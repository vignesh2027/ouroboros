"""The multi-hop research agent, in standard and guarded modes.

Each hop: query, fetch, retrieve, read (the model states a belief, stances and
its next query), measure (BAQD, balance, diversity), then in guarded mode the
guard may replace the next query with a counter-query (CQI). After the last hop
the model writes a final answer, which is then audited claim by claim.

Standard and guarded runs use identical read prompts. Guarded differs only in
the CQI guard and the Balanced Evidence Buffer synthesis prompt.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict

from . import audit as audit_mod
from .audit import DATA_NOTICE, clean_passage_text, format_passages, parse_cited_pids
from .live_metrics import source_diversity
from .metric import baqd as baqd_fn
from .rag import EvidencePool, Passage
from .retrieval import Encoder
from .sources import search_all

log = logging.getLogger("ouroboros.agent")

NEUTRAL_IN_SYNTHESIS = 4
STANCES = ("supports", "contradicts", "neutral")


@dataclass
class AgentConfig:
    mode: str = "guarded"          # "standard" | "guarded"
    hops: int = 4
    k: int = 6                     # passages read per hop
    per_source: int = 3            # documents fetched per source per hop
    sources: list[str] | None = None
    baqd_threshold: float = 0.05   # CQI fires when BAQD(n) > this ...
    skew_threshold: float = 0.5    # ... or |skew| at this hop >= this
    corpus: list[Passage] | None = None   # closed-corpus mode: no web fetching


READ_SCHEMA = {
    "type": "object",
    "properties": {
        "stances": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pid": {"type": "string"},
                    "stance": {"type": "string", "enum": list(STANCES)},
                    "reason": {"type": "string"},
                },
                "required": ["pid", "stance", "reason"],
                "additionalProperties": False,
            },
        },
        "belief": {"type": "string"},
        "confidence": {"type": "integer"},
        "next_query": {"type": "string"},
    },
    "required": ["stances", "belief", "confidence", "next_query"],
    "additionalProperties": False,
}

CQI_SCHEMA = {
    "type": "object",
    "properties": {"counter_query": {"type": "string"}, "why": {"type": "string"}},
    "required": ["counter_query", "why"],
    "additionalProperties": False,
}

SYNTH_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "integer"},
        "one_line": {"type": "string"},
    },
    "required": ["answer", "confidence", "one_line"],
    "additionalProperties": False,
}


class Cancelled(Exception):
    """The caller asked the run to stop (for example the browser disconnected)."""


class _CancelLLM:
    """Wraps an LLM so every model call first checks a cancel flag."""

    def __init__(self, llm, cancel):
        self._llm, self._cancel = llm, cancel

    def _check(self):
        if self._cancel is not None and self._cancel.is_set():
            raise Cancelled("The run was stopped.")

    def json(self, *a, **kw):
        self._check()
        return self._llm.json(*a, **kw)

    def text(self, *a, **kw):
        self._check()
        return self._llm.text(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._llm, name)


# ---------------------------------------------------------------- helpers

def _clamp_conf(value, default=None):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def _words(text: str, n: int) -> str:
    w = (text or "").split()
    return " ".join(w[:n])


def _config_dict(cfg: AgentConfig) -> dict:
    d = asdict(cfg)
    corpus = d.pop("corpus", None)
    d["closed_corpus"] = corpus is not None
    d["corpus_size"] = len(corpus) if corpus is not None else 0
    return d


def _usage_delta(llm, before: dict) -> dict:
    now = dict(llm.usage)
    out = {k: now.get(k, 0) - before.get(k, 0) for k in
           ("calls", "cached_calls", "input_tokens", "output_tokens")}
    out["cost_usd"] = round(now.get("cost_usd", 0.0) - before.get("cost_usd", 0.0), 6)
    return out


def _fit_encoder(pool: EvidencePool, texts: list[str]):
    corpus = [f"{p.title} {p.text}" for p in pool.passages()] + texts
    try:
        return Encoder(corpus)
    except ValueError:  # nothing but stop words
        return None


def _hop_baqd(pool, question, query, prev_belief, texts):
    """BAQD for this hop's query against the previous belief. None at hop 1."""
    if not prev_belief:
        return None
    enc = _fit_encoder(pool, texts)
    if enc is None:
        return None
    return float(baqd_fn(enc.encode(query), enc.encode(prev_belief), enc.encode(question)))


def _skew(support: int, contradict: int) -> float:
    return (support - contradict) / max(1, support + contradict)


# ---------------------------------------------------------------- prompts

def _read_prompts(question, belief, passages):
    system = (
        "You are a research agent answering a question over several rounds of search. "
        "Each round you read some retrieved passages, state what you now believe, and "
        "write the search you would run next. Be honest about uncertainty. "
        + DATA_NOTICE
    )
    belief_line = clean_passage_text(belief) if belief else "(none yet, this is your first round)"
    user = (
        f"Question: {question}\n\nYour belief after the previous round: {belief_line}\n\n"
        f"Passages retrieved this round:\n{format_passages(passages)}\n\n"
        "Do four things.\n"
        "1. Write your belief now: one sentence saying what you believe the answer to the "
        "question is.\n"
        "2. For every passage, give its stance relative to the belief you wrote in step 1: "
        "supports, contradicts, or neutral (off topic, or takes no side). Add a reason of "
        "at most 20 words. Copy each pid exactly.\n"
        "3. Give your confidence from 0 to 100.\n"
        "4. Write next_query: the search you would run next to finish answering, at most "
        "14 words."
    )
    return system, user


def _cqi_prompts(question, belief, original_query, passages):
    system = (
        "You are a research agent that guards against confirmation bias. Your current "
        "belief may be wrong. You write a search query that deliberately looks for evidence "
        "that CONTRADICTS the belief. " + DATA_NOTICE
    )
    seen = format_passages(passages, max_chars=300)
    user = (
        f"Question: {question}\n\nCurrent belief: {clean_passage_text(belief)}\n\n"
        f"The query you were about to run: {clean_passage_text(original_query)}\n\n"
        f"Passages read so far this round:\n{seen}\n\n"
        "Write counter_query: a neutral-sounding web search of at most 14 words whose "
        "results would most likely contradict, limit or complicate the current belief "
        "(for example evidence of no effect, harms, exceptions or opposing studies). Do not "
        "restate the belief. In why, explain in one sentence what the counter-query looks for."
    )
    return system, user


def _synth_prompts(question, mode, support, contradict, neutral, all_read):
    base = (
        "You write the final answer to a research question from retrieved passages. "
        "Write 120 to 220 words of plain prose. Every factual sentence must end with one or "
        "more citations in square brackets using the exact pid, for example [abc123#2]. Cite "
        "only pids that appear in the passages, and make no claim the passages do not back. "
        "Also give a confidence from 0 to 100 and a one_line summary of at most 25 words. "
        + DATA_NOTICE
    )
    if mode == "guarded":
        system = base + (
            " BALANCED EVIDENCE BUFFER: the passages are split into a supporting group and a "
            "contradicting group. If the contradicting group is not empty you MUST weigh both "
            "sides in the answer: say what the contradicting evidence shows, how strong each "
            "side is, and let your confidence reflect the disagreement. Do not bury or skip "
            "the contradicting side."
        )
        user = (
            f"Question: {question}\n\n"
            f"SUPPORTING passages:\n{format_passages(support) or '(none)'}\n\n"
            f"CONTRADICTING passages:\n{format_passages(contradict) or '(none)'}\n\n"
            f"OTHER passages (neutral):\n{format_passages(neutral) or '(none)'}\n\n"
            "Write the answer."
        )
    else:
        system = base
        user = (
            f"Question: {question}\n\nPassages:\n{format_passages(all_read)}\n\n"
            "Write the answer."
        )
    return system, user


def _tidy_citations(answer: str, pool: EvidencePool) -> str:
    """Drop [pid] markers that do not name a passage in the pool."""
    import re

    def repl(m):
        toks = [t for t in re.split(r"[\s,;]+", m.group(1).strip()) if t]
        if not toks or not all("#" in t for t in toks):
            return m.group(0)
        keep = [t for t in toks if t in pool]
        return "[" + ", ".join(keep) + "]" if keep else ""
    out = re.sub(r"\[([^\[\]]{1,200})\]", repl, answer)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


# ---------------------------------------------------------------- the loop

def run(question: str, cfg: AgentConfig, llm, emit=lambda event: None, cancel=None) -> dict:
    """Run the agent. `cancel` is an optional threading.Event checked before each hop
    and before every model call; when set, the run stops and returns a record with
    record["cancelled"] = True."""
    t0 = time.time()
    raw_llm = llm
    llm = _CancelLLM(raw_llm, cancel)
    before = dict(llm.usage)
    mode = cfg.mode if cfg.mode in ("standard", "guarded") else "guarded"
    guarded = mode == "guarded"
    hops_total = max(1, int(cfg.hops))
    config = _config_dict(cfg)
    config["mode"] = mode
    config["hops"] = hops_total
    offline = bool(getattr(llm, "offline", False))

    record: dict = {"question": question, "mode": mode, "config": config, "hops": [],
                    "cqi_events": [], "synthesis": None, "audit": None}
    emit({"type": "start", "question": question, "mode": mode, "config": config})

    try:
        pool = EvidencePool()
        if cfg.corpus is not None:
            pool.add_passages(cfg.corpus)

        read: dict[str, str] = {}          # pid -> stance, over every hop
        read_score: dict[str, float] = {}  # pid -> hybrid retrieval score when it was read
        read_order: list[str] = []
        texts: list[str] = [question]      # question, every query and belief so far
        belief = ""                        # belief after the previous hop
        confidence = None
        pending_query = question
        origin = "question"

        for hop in range(1, hops_total + 1):
            llm._check()
            query = pending_query
            texts.append(query)
            hop_rec: dict = {"hop": hop}

            ev = {"type": "hop_query", "hop": hop, "query": query, "origin": origin}
            emit(ev)
            hop_rec.update({k: v for k, v in ev.items() if k != "type"})

            # fetch
            fetched: dict[str, int] = {}
            if cfg.corpus is None:
                try:
                    docs = search_all(query, per_source=cfg.per_source, sources=cfg.sources,
                                      offline=offline)
                except Exception as e:
                    log.warning("search failed: %s", e)
                    docs = []
                for d in docs:
                    fetched[d.source] = fetched.get(d.source, 0) + 1
                pool.add_documents(docs)
            ev = {"type": "hop_sources", "hop": hop, "fetched": fetched, "pool_size": len(pool)}
            emit(ev)
            hop_rec.update({k: v for k, v in ev.items() if k != "type"})

            # retrieve
            exclude = set(read)
            found = pool.search(query, k=cfg.k, exclude=exclude)
            if not found:
                found = pool.search(question, k=cfg.k, exclude=exclude)

            # read
            if found:
                system, user = _read_prompts(question, belief, found)
                out = llm.json(system, user, READ_SCHEMA, max_tokens=1500, effort="low",
                               tag="read")
                said = {}
                for s in out.get("stances") or []:
                    if s.get("pid") and s.get("stance") in STANCES:
                        said[s["pid"]] = (s["stance"], str(s.get("reason") or "").strip())
                rows = []
                for p in found:
                    stance, reason = said.get(p.pid, ("neutral", "The model gave no stance for this passage."))
                    rows.append({"pid": p.pid, "title": p.title, "url": p.url,
                                 "domain": p.domain, "source": p.source, "year": p.year,
                                 "text": p.text, "stance": stance, "reason": reason})
                    read[p.pid] = stance
                    read_score[p.pid] = p.score
                    read_order.append(p.pid)
                new_belief = str(out.get("belief") or "").strip() or belief
                confidence = _clamp_conf(out.get("confidence"), confidence)
                next_query = _words(str(out.get("next_query") or "").strip(), 14) or question
            else:
                rows, new_belief, next_query = [], belief, pending_query
            ev = {"type": "hop_read", "hop": hop, "passages": rows, "belief": new_belief,
                  "confidence": confidence, "next_query": next_query}
            emit(ev)
            hop_rec.update({k: v for k, v in ev.items() if k != "type"})
            if new_belief:
                texts.append(new_belief)

            # metrics
            sup = sum(1 for r in rows if r["stance"] == "supports")
            con = sum(1 for r in rows if r["stance"] == "contradicts")
            neu = len(rows) - sup - con
            skew = _skew(sup, con)
            div = source_diversity(rows)
            hop_baqd = _hop_baqd(pool, question, query, belief, texts)
            cum = {"support": sum(1 for s in read.values() if s == "supports"),
                   "contradict": sum(1 for s in read.values() if s == "contradicts"),
                   "neutral": sum(1 for s in read.values() if s == "neutral"),
                   "passages": len(read)}
            ev = {"type": "hop_metrics", "hop": hop, "baqd": hop_baqd, "support": sup,
                  "contradict": con, "neutral": neu, "skew": skew,
                  "balance_loss": abs(skew), "domains": div["domains"],
                  "sources": div["sources"], "cumulative": cum}
            emit(ev)
            hop_rec.update({k: v for k, v in ev.items() if k != "type"})

            # guard: only when another hop follows
            pending_query, origin = next_query, "model"
            if guarded and hop < hops_total:
                fire = ((hop_baqd is not None and hop_baqd > cfg.baqd_threshold)
                        or abs(skew) >= cfg.skew_threshold)
                if fire and new_belief:
                    system, user = _cqi_prompts(question, new_belief, next_query, found)
                    out = llm.json(system, user, CQI_SCHEMA, max_tokens=400, effort="low",
                                   tag="cqi")
                    counter = _words(str(out.get("counter_query") or "").strip(), 14)
                    if counter:
                        ev = {"type": "cqi", "hop": hop,
                              "trigger": {"baqd": hop_baqd, "skew": skew},
                              "original_query": next_query, "counter_query": counter,
                              "why": str(out.get("why") or "").strip()}
                        emit(ev)
                        record["cqi_events"].append({k: v for k, v in ev.items() if k != "type"})
                        hop_rec["cqi"] = True
                        pending_query, origin = counter, "counter"
            belief = new_belief
            record["hops"].append(hop_rec)

        # synthesis
        by_pid = {pid: pool.get(pid) for pid in read_order}
        sup_p = [by_pid[p] for p in read_order if read[p] == "supports"]
        con_p = [by_pid[p] for p in read_order if read[p] == "contradicts"]
        neu_p = sorted((by_pid[p] for p in read_order if read[p] == "neutral"),
                       key=lambda p: (-read_score.get(p.pid, 0.0), p.pid))[:NEUTRAL_IN_SYNTHESIS]
        if not read_order:
            synth = {"answer": "No evidence could be retrieved for this question, so no "
                               "answer is given.", "confidence": 0,
                     "one_line": "No evidence was retrieved."}
            audit_report = audit_mod.empty_report(len(pool), 0)
        else:
            chosen = sup_p + con_p + neu_p
            order = {pid: i for i, pid in enumerate(read_order)}
            chosen.sort(key=lambda p: order[p.pid])
            system, user = _synth_prompts(question, mode, sup_p, con_p, neu_p, chosen)
            out = llm.json(system, user, SYNTH_SCHEMA, max_tokens=1500, effort="low",
                           tag="synthesis")
            answer = _tidy_citations(str(out.get("answer") or "").strip(), pool)
            synth = {"answer": answer, "confidence": _clamp_conf(out.get("confidence"), None),
                     "one_line": str(out.get("one_line") or "").strip()}
            audit_report = None
        record["synthesis"] = synth
        emit({"type": "synthesis", **synth})

        if audit_report is None:
            audit_report = audit_mod.audit_answer(
                question, synth["answer"], pool, llm,
                cited_pids=parse_cited_pids(synth["answer"]),
                fetch_more=cfg.corpus is None, sources=cfg.sources,
                stated_confidence=synth["confidence"])
        record["audit"] = audit_report
        emit({"type": "audit", "report": audit_report})
    except Exception as e:
        msg = (f"{type(e).__name__}: {e}")[:400]
        log.warning("agent run failed: %s", msg)
        record["error"] = msg
        if isinstance(e, Cancelled):
            record["cancelled"] = True
        record["usage"] = _usage_delta(raw_llm, before)
        record["seconds"] = round(time.time() - t0, 2)
        emit({"type": "error", "message": msg})
        return record

    record["usage"] = _usage_delta(raw_llm, before)
    record["seconds"] = round(time.time() - t0, 2)
    emit({"type": "done", "run_id": None, "usage": record["usage"],
          "seconds": record["seconds"]})
    return record
