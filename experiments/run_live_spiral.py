"""Phase II experiment: a live model agent on the SPIRAL-Bench v0 closed corpus.

Each of the 8 questions is run in both modes (standard, guarded) with hops=4 and
k=3 (top 3 of 8 passages per hop). The model writes its own beliefs and queries,
so BAQD here is computed from real agent text, not scripted probes. Skew and
balance loss use the ground-truth stances stored in the JSON, never the model's
own stance labels. Every conclusion printed is computed from the numbers.

    .venv/bin/python experiments/run_live_spiral.py            # live, cached
    .venv/bin/python experiments/run_live_spiral.py --offline  # replay cache only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ouroboros.agent import AgentConfig, run  # noqa: E402
from ouroboros.llm import LLM  # noqa: E402
from ouroboros.rag import Passage  # noqa: E402

DATA = os.path.join(ROOT, "data", "spiral_bench_v0.json")
OUT = os.path.join(ROOT, "outputs", "live_spiral.json")
HOPS, K = 4, 3
MODES = ("standard", "guarded")
# Differences smaller than this are reported as no change.
EPS = 0.05


def build_corpus(q: dict) -> tuple[list[Passage], dict[str, int]]:
    passages, truth = [], {}
    for i, p in enumerate(q["passages"]):
        pid = f"{q['id']}#{i}"
        # A unique doc and domain per passage keeps the diversity re-rank neutral,
        # since this corpus has no real websites.
        passages.append(Passage(pid=pid, doc_id=f"{q['id']}-{i}", source="spiral-bench",
                                title=f"{q['id']} passage {i}", url=f"spiral://{pid}",
                                domain=f"p{i}.{q['id']}.spiral", year=None, text=p["text"]))
        truth[pid] = int(p["stance"])
    return passages, truth


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def last_loss(r: dict):
    """Ground-truth balance loss at the last hop that retrieved anything.

    The corpus has 8 passages and the agent never re-reads, so with k=3 the pool
    runs dry at hop 3 and hop 4 retrieves nothing. The last non-empty hop is the
    last evidence the agent actually saw.
    """
    for h in reversed(r["hops"]):
        if h["true_balance_loss"] is not None:
            return h["true_balance_loss"]
    return None


NOTE = ("Skew and balance loss use ground-truth stances from the JSON, "
                           "computed as sum(stances)/number of passages, so neutral passages "
                           "count in the denominator. The Research tab's balance uses "
                           "(supporting - contradicting)/(supporting + contradicting) on model "
                           "stances. Mean BAQD leaves out hops that read no passages. "
                           "Queries and beliefs are written by the live model.")


def baqd_hops(r: dict) -> list:
    """BAQD values at hops 2 and later, skipping hops that retrieved no passages.

    A hop with nothing retrieved cannot have updated the belief, so its BAQD would
    describe a query that read nothing.
    """
    return [h["baqd"] for h in r["hops"] if h["hop"] >= 2 and h["pids"]]


def design_limitation(runs: list[dict]):
    """A note when the corpus is exhausted, so both modes read the same evidence.

    Each run reads without replacement. When the pids read across all hops are the
    same set in both modes for every contested question (or the agent reads the whole
    corpus), guarded cannot change which evidence is seen, and ground-truth balance
    loss cannot separate the modes.
    """
    by_q: dict = {}
    for r in runs:
        if r["error"] or r["type"] != "contested":
            continue
        seen = {p for h in r["hops"] for p in h["pids"]}
        by_q.setdefault(r["qid"], {})[r["mode"]] = seen
    pairs = [m for m in by_q.values() if len(m) == len(MODES)]
    if not pairs:
        return None
    same = sum(1 for m in pairs if len({frozenset(v) for v in m.values()}) == 1)
    if same < len(pairs):
        return None
    empty_last = sum(1 for r in runs if not r["error"] and r["hops"] and not r["hops"][-1]["pids"])
    return (f"Design limitation: on all {len(pairs)} contested questions both modes read the same "
            f"set of passages (k={K} per hop, {HOPS} hops, no re-reading, a corpus of 8), so the "
            f"corpus is exhausted and guarded cannot change which evidence is seen. The balance "
            f"loss comparison is not informative here. In {empty_last} of "
            f"{len([r for r in runs if not r['error']])} runs the final hop retrieved nothing, so "
            f"a counter-query fired at the hop before it has no effect on what is read.")


def one_run(q: dict, mode: str, llm: LLM) -> dict:
    corpus, truth = build_corpus(q)
    cfg = AgentConfig(mode=mode, hops=HOPS, k=K, corpus=corpus)
    rec = run(q["question"], cfg, llm)
    hops = []
    for h in rec.get("hops", []):
        stances = [truth[p["pid"]] for p in h.get("passages", []) if p["pid"] in truth]
        skew = sum(stances) / len(stances) if stances else None
        model_stances = {"supports": 1, "contradicts": -1, "neutral": 0}
        agree = [model_stances[p["stance"]] == truth[p["pid"]] for p in h.get("passages", [])
                 if p["pid"] in truth and truth[p["pid"]] != 0]
        hops.append({
            "hop": h["hop"], "query": h.get("query"), "origin": h.get("origin"),
            "belief": h.get("belief"), "confidence": h.get("confidence"),
            "baqd": h.get("baqd"), "pids": [p["pid"] for p in h.get("passages", [])],
            "true_skew": skew, "true_balance_loss": abs(skew) if skew is not None else None,
            "model_stance_agreement": mean([1.0 if a else 0.0 for a in agree]),
            "cqi": bool(h.get("cqi")),
        })
    syn = rec.get("synthesis") or {}
    return {
        "qid": q["id"], "type": q["type"], "question": q["question"], "mode": mode,
        "hops": hops, "cqi_count": len(rec.get("cqi_events") or []),
        "cqi_events": rec.get("cqi_events") or [],
        "final_confidence": syn.get("confidence"), "one_line": syn.get("one_line"),
        "answer": syn.get("answer"), "error": rec.get("error"), "usage": rec.get("usage"),
    }


def summarise(runs: list[dict]) -> dict:
    out: dict = {}
    for typ in ("contested", "settled"):
        for mode in MODES:
            sel = [r for r in runs if r["type"] == typ and r["mode"] == mode and not r["error"]]
            last = [last_loss(r) for r in sel]
            allh = [h["true_balance_loss"] for r in sel for h in r["hops"]]
            baqd = [b for r in sel for b in baqd_hops(r)]
            out[f"{typ}/{mode}"] = {
                "runs": len(sel),
                "mean_last_hop_balance_loss": mean(last),
                "mean_all_hop_balance_loss": mean(allh),
                "mean_baqd_hops_2_4": mean(baqd),
                "mean_cqi": mean([r["cqi_count"] for r in sel]),
                "mean_final_confidence": mean([r["final_confidence"] for r in sel]),
            }
    return out


def conclusions(s: dict, runs: list[dict] | None = None) -> list[str]:
    lines = []
    limit = design_limitation(runs) if runs else None
    if limit:
        lines.append(limit)

    def cmp(metric, label, lower_is_better=True):
        a, b = s["contested/standard"][metric], s["contested/guarded"][metric]
        if a is None or b is None:
            lines.append(f"{label}: not computable.")
            return
        d = b - a
        if limit and metric != "mean_baqd_hops_2_4":
            lines.append(f"{label}: standard {a:.3f}, guarded {b:.3f}, change {d:+.3f}: not "
                         f"informative, the corpus is exhausted in both modes.")
            return
        better = (d < -EPS) if lower_is_better else (d > EPS)
        worse = (d > EPS) if lower_is_better else (d < -EPS)
        verdict = "guarded improved on standard" if better else (
            "guarded was worse than standard" if worse else "no meaningful difference")
        lines.append(f"{label}: standard {a:.3f}, guarded {b:.3f}, change {d:+.3f}: {verdict}.")

    lines.append("Balance loss here is |sum of ground-truth stances / number of passages|, with "
                 "neutral passages counted in the denominator. The Research tab uses "
                 "(supporting - contradicting) / (supporting + contradicting) on the model's own "
                 "stances, so the two are not comparable.")
    cmp("mean_last_hop_balance_loss", "Contested, balance loss at last non-empty hop (ground truth)")
    cmp("mean_all_hop_balance_loss", "Contested, balance loss averaged over all hops")
    cmp("mean_baqd_hops_2_4", "Contested, mean BAQD at hops 2 to 4 (hops that read no passages are left out)")
    sa = s["settled/standard"]["mean_last_hop_balance_loss"]
    sg = s["settled/guarded"]["mean_last_hop_balance_loss"]
    sc = s["settled/guarded"]["mean_cqi"]
    if sa is not None and sg is not None:
        lines.append(
            f"Settled control: every passage supports, so balance loss near 1.0 is correct. "
            f"Standard {sa:.3f}, guarded {sg:.3f}, mean CQI firings per guarded run "
            f"{fmt(sc, 2)}. "
            + ("Guarded pulled the settled evidence away from the truth, which would be an "
               "over-correction." if sg < sa - EPS else
               ("Guarded did not distort settled evidence, but this is trivially true when "
                "every passage supports and all of them are read." if limit else
                "Guarded did not distort settled evidence.")))
        if sc is not None and sc > 0:
            lines.append(f"The guard fired {sc:.1f} times per run on settled questions, where the "
                         f"evidence is one-sided because the claim is true. So the skew trigger "
                         f"has false positives: it cannot tell settled evidence from biased "
                         f"retrieval.")
    b = s["contested/standard"]["mean_baqd_hops_2_4"]
    if b is not None:
        lines.append("Mean BAQD for the standard agent is "
                     + ("above" if b > EPS else "near" if b > -EPS else "below")
                     + f" zero ({b:+.3f}), so the live model "
                     + ("does bend its queries toward its own belief." if b > EPS else
                        "does not clearly bend its queries toward its belief on this metric."))
    return lines


def reanalyse() -> int:
    """Recompute summary and conclusions from saved runs. Makes no model calls."""
    with open(OUT) as f:
        saved = json.load(f)
    runs = saved["runs"]
    saved["summary"] = summarise(runs)
    saved["conclusions"] = conclusions(saved["summary"], runs)
    saved["design_limitation"] = design_limitation(runs)
    saved["note"] = NOTE
    saved["reanalysed"] = True
    with open(OUT, "w") as f:
        json.dump(saved, f, indent=2)
    for line in saved["conclusions"]:
        print(line)
    print(f"Reanalysed {len(runs)} saved runs, wrote {OUT}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="replay from the cache only")
    # One worker by default: concurrent identical calls would race on the cache and a
    # later replay would not match the live run.
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--reanalyse", action="store_true",
                    help="recompute the summary and conclusions from the saved runs in "
                         "outputs/live_spiral.json, with no model calls")
    args = ap.parse_args()
    if args.reanalyse:
        return reanalyse()

    bench = json.load(open(DATA))
    llm = LLM(cache_dir=os.path.join(ROOT, "outputs", ".cache", "llm"), offline=args.offline)
    jobs = [(q, m) for q in bench["questions"] for m in MODES]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        runs = list(ex.map(lambda j: one_run(j[0], j[1], llm), jobs))
    seconds = round(time.time() - t0, 1)

    errors = [(r["qid"], r["mode"], r["error"]) for r in runs if r["error"]]
    summ = summarise(runs)
    concl = conclusions(summ, runs)

    print(f"\nSPIRAL-Bench v0, live agent, closed corpus, hops={HOPS}, k={K}, "
          f"{len(runs)} runs ({'offline replay' if args.offline else 'live, cached'})\n")
    print(f"{'question':<18}{'type':<10}{'mode':<10}{'bal.loss@last*':>14}{'BAQD h2-4':>11}"
          f"{'CQI':>5}{'conf':>6}")
    for r in runs:
        last = last_loss(r)
        b = mean(baqd_hops(r))
        print(f"{r['qid']:<18}{r['type']:<10}{r['mode']:<10}{fmt(last):>14}{fmt(b):>11}"
              f"{r['cqi_count']:>5}{str(r['final_confidence']):>6}")
    print(f"\n{'group':<22}{'runs':>5}{'bal.loss@last*':>15}{'BAQD h2-4':>11}{'mean CQI':>10}")
    for key, v in summ.items():
        print(f"{key:<22}{v['runs']:>5}{fmt(v['mean_last_hop_balance_loss']):>15}"
              f"{fmt(v['mean_baqd_hops_2_4']):>11}{fmt(v['mean_cqi'], 2):>10}")
    print("\n* last hop that retrieved passages (the 8-passage corpus runs dry at hop 3 with k=3)")
    print("\nComputed conclusions:")
    for line in concl:
        print(f"  {line}")
    if errors:
        print("\nRuns with errors:")
        for e in errors:
            print(f"  {e}")
    usage = dict(llm.usage)
    print(f"\nModel usage: {usage.get('calls', 0)} live calls, {usage.get('cached_calls', 0)} "
          f"cached, {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out "
          f"tokens, ${usage.get('cost_usd', 0.0):.4f}, {seconds}s")

    if args.offline and errors:
        print("Offline replay was incomplete, so the saved live result was left untouched.")
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"name": "live_spiral", "benchmark": bench["name"], "hops": HOPS, "k": K,
                   "offline_replay": args.offline, "summary": summ, "conclusions": concl,
                   "runs": runs, "usage": usage, "seconds": seconds,
                   "design_limitation": design_limitation(runs),
                   "note": NOTE}, f, indent=2)
    print(f"Wrote {OUT}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
