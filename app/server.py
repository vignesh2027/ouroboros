"""Ouroboros platform server (SPEC section 4).

Run from the repo root:
    .venv/bin/python -m uvicorn app.server:app --port 8000

ouroboros.agent, ouroboros.audit and ouroboros.llm are imported lazily inside
handlers so this module loads even while those modules are being written.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import threading
import time
import zlib
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
STATIC_DIR = APP_DIR / "static"
RUNS_DIR = APP_DIR / "runs"
OUTPUTS_DIR = ROOT / "outputs"
LLM_CACHE = str(OUTPUTS_DIR / ".cache" / "llm")
KEEPALIVE_SECONDS = 10.0
MAX_ANSWER_CHARS = 8000
MAX_QUESTION_CHARS = 500

app = FastAPI(title="Ouroboros", docs_url=None, redoc_url=None, openapi_url=None)
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class _CachedStatic(StaticFiles):
    """Static files with a short revalidating cache, so edits show up on reload."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if resp.status_code in (200, 304):
            resp.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
        return resp


app.mount("/static", _CachedStatic(directory=str(STATIC_DIR), check_dir=False), name="static")


def is_offline() -> bool:
    return os.environ.get("OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def _public_demo() -> bool:
    """PUBLIC_DEMO=1 on a public host: no source files, featured runs only, live calls rate limited."""
    return os.environ.get("PUBLIC_DEMO", "").strip().lower() in ("1", "true", "yes", "on")


# Questions whose saved runs a public host lists in Recent research.
FEATURED_QUESTIONS = frozenset({
    "Is intermittent fasting effective for weight loss?",
    "Which is the fastest production motorcycle sold in India?",
    "Does remote work increase productivity?",
    "Is nuclear power a good way to cut carbon emissions?",
    "Should adults take vitamin D supplements daily?",
    "Does raising the minimum wage reduce employment?",
    "Is coffee good for heart health?",
})

# Live model calls on a public host: per visitor per hour, and for the whole site per day.
PUBLIC_PER_IP_HOUR = int(os.environ.get("PUBLIC_PER_IP_HOUR", "10"))
PUBLIC_PER_DAY = int(os.environ.get("PUBLIC_PER_DAY", "150"))
LIMIT_MESSAGE = ("This public demo has reached its limit for new questions for now. "
                 "The saved example questions still work.")
_limit_lock = threading.Lock()
_limit_hits: dict = {}      # ip -> list of timestamps in the last hour
_limit_day = {"day": "", "count": 0}


def _take_public_quota(ip: str, cost: int = 1) -> bool:
    """Record cost live calls for ip. False when the hourly or daily limit is reached."""
    now = time.time()
    day = time.strftime("%Y-%m-%d")
    with _limit_lock:
        if _limit_day["day"] != day:
            _limit_day.update(day=day, count=0)
        recent = [t for t in _limit_hits.get(ip, []) if now - t < 3600]
        if len(recent) + cost > PUBLIC_PER_IP_HOUR or _limit_day["count"] + cost > PUBLIC_PER_DAY:
            _limit_hits[ip] = recent
            return False
        _limit_hits[ip] = recent + [now] * cost
        _limit_day["count"] += cost
        return True


_LIMITED = {"/api/research/stream": 1, "/api/compare/stream": 2, "/api/audit": 1, "/api/plain": 1}


@app.middleware("http")
async def _public_limits(request: Request, call_next):
    cost = _LIMITED.get(request.url.path)
    if not cost or not _public_demo() or is_offline():
        return await call_next(request)
    if request.url.path.endswith("/stream"):
        q = (request.query_params.get("q") or "").strip()
        modes = ("standard", "guarded") if "compare" in request.url.path else \
            (request.query_params.get("mode") or "guarded",)
        if not request.query_params.get("prev") and all(find_saved_run(q, m) for m in modes):
            return await call_next(request)  # a saved question replays from the cache for free
    ip = request.client.host if request.client else "unknown"
    if _take_public_quota(ip, cost):
        return await call_next(request)
    if request.url.path.endswith("/stream"):
        return StreamingResponse(iter([sse({"type": "error", "message": LIMIT_MESSAGE})]),
                                 media_type="text/event-stream")
    return JSONResponse({"error": LIMIT_MESSAGE}, status_code=429)


# --------------------------------------------------------------------------
# Credentials (presence only, the value is never read into a response)
# --------------------------------------------------------------------------

def credentials_kind() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "api_key"
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "oauth_token"
    try:
        if (Path.home() / ".config" / "anthropic" / "credit-key").is_file():
            return "oauth_token"
    except OSError:
        pass
    return "none"


def make_llm():
    from ouroboros.llm import LLM
    return LLM(cache_dir=LLM_CACHE, offline=is_offline())


# --------------------------------------------------------------------------
# Code viewer allow-list
# --------------------------------------------------------------------------

_PKG_FILE = re.compile(r"^(ouroboros|tests)/[A-Za-z0-9_]+\.py$")
_EXACT_FILES = frozenset({
    "experiments/run_live_spiral.py",
    "run_experiment.py",
    "run_diagnostic.py",
})


# Files that deal with the hosted service connection stay out of the browser.
_HIDDEN_CODE = frozenset({"ouroboros/llm.py", "tests/test_llm.py", "app/server.py",
                          "tests/test_server.py", "tests/test_chat.py"})


def resolve_code_path(path: str) -> Path | None:
    """Return the real file for an allow-listed relative path, else None."""
    if not isinstance(path, str) or not path or len(path) > 200:
        return None
    if path in _HIDDEN_CODE:
        return None
    if "\x00" in path or "\\" in path or path.startswith("/") or ".." in path:
        return None
    if not (_PKG_FILE.match(path) or path in _EXACT_FILES):
        return None
    full = ROOT / path
    try:
        real = full.resolve(strict=True)
        rel = real.relative_to(ROOT.resolve()).as_posix()
        # The resolved file must itself be the allow-listed path: no symlink to another
        # file, and no case alias on a case-insensitive filesystem.
        if rel != path or real.name not in {x.name for x in real.parent.iterdir()}:
            return None
    except (OSError, ValueError):
        return None
    if not real.is_file():
        return None
    return real


def list_code_files() -> list[str]:
    out: list[str] = []
    for sub in ("ouroboros", "tests"):
        d = ROOT / sub
        if d.is_dir():
            for p in sorted(d.glob("*.py")):
                rel = f"{sub}/{p.name}"
                if resolve_code_path(rel):
                    out.append(rel)
    for rel in sorted(_EXACT_FILES):
        if resolve_code_path(rel):
            out.append(rel)
    return out


# --------------------------------------------------------------------------
# Benchmark summary (Phase I)
# --------------------------------------------------------------------------

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def parse_phase1(traces_path: Path, diagnostic_path: Path) -> dict | None:
    rows = []
    if traces_path.is_file():
        for line in traces_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    diag = None
    if diagnostic_path.is_file():
        try:
            diag = json.loads(diagnostic_path.read_text())
        except ValueError:
            diag = None
    if not rows and diag is None:
        return None

    questions: dict[str, dict] = {}
    for r in rows:
        q = questions.setdefault(r["question_id"], {"id": r["question_id"], "type": r.get("type"), "arms": {}})
        q["arms"].setdefault(r["arm"], []).append({
            "hop": r["hop"], "query": r.get("query"), "baqd": r.get("baqd"),
            "support": r.get("support"), "oppose": r.get("oppose"),
            "skew": r.get("skew"), "balance_loss": r.get("balance_loss"),
        })
    for q in questions.values():
        for hops in q["arms"].values():
            hops.sort(key=lambda h: h["hop"])

    # mean balance loss and BAQD by arm, type and hop
    by_group: dict[tuple, dict] = {}
    for r in rows:
        g = by_group.setdefault((r.get("type"), r["arm"], r["hop"]), {"bl": [], "baqd": []})
        g["bl"].append(r.get("balance_loss"))
        g["baqd"].append(r.get("baqd"))
    mean_by_group = [
        {"type": t, "arm": a, "hop": h, "n": len(v["bl"]),
         "mean_balance_loss": _mean(v["bl"]), "mean_baqd": _mean(v["baqd"])}
        for (t, a, h), v in sorted(by_group.items(), key=lambda kv: (str(kv[0][0]), kv[0][1], kv[0][2]))
    ]
    last_hop = max((r["hop"] for r in rows), default=None)
    final = {}
    for r in rows:
        if r["hop"] == last_hop:
            final.setdefault(r["arm"], {}).setdefault(r.get("type"), []).append(r.get("balance_loss"))
    final_mean = {a: {t: _mean(v) for t, v in d.items()} for a, d in final.items()}

    diag_summary = None
    if isinstance(diag, list):
        keys = ["neutral", "drift_hop3", "oracle_support", "oracle_oppose", "shared_vocab_ratio"]
        diag_summary = {
            "rows": diag,
            "means": {k: _mean([d.get(k) for d in diag]) for k in keys},
            "n": len(diag),
        }
    return {
        "n_trace_rows": len(rows),
        "n_questions": len(questions),
        "hops": last_hop,
        "arms": sorted({r["arm"] for r in rows}),
        "questions": list(questions.values()),
        "mean_by_type_arm_hop": mean_by_group,
        "final_hop_mean_balance_loss": final_mean,
        "diagnostic": diag_summary,
    }


def build_benchmark() -> dict:
    phase1 = parse_phase1(OUTPUTS_DIR / "traces.jsonl", OUTPUTS_DIR / "diagnostic.json")
    phase2 = None
    p2 = OUTPUTS_DIR / "live_spiral.json"
    if p2.is_file():
        try:
            phase2 = json.loads(p2.read_text())
        except ValueError:
            phase2 = None
    return {"phase1": phase1, "phase2": phase2}


# --------------------------------------------------------------------------
# Saved runs
# --------------------------------------------------------------------------

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9\-]{0,120}$")


def make_run_id(question: str, mode: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:48].strip("-") or "run"
    h = hashlib.sha1(f"{question}|{mode}|{time.time_ns()}".encode()).hexdigest()[:6]
    return f"{slug}-{mode}-{h}"


def save_run(run_id: str, record: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record["run_id"] = run_id
    record["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = RUNS_DIR / f".{run_id}.tmp"
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    os.replace(tmp, RUNS_DIR / f"{run_id}.json")


def _is_replayable(record: dict) -> bool:
    """A run worth keeping: it finished, read some evidence and produced an audit."""
    if not isinstance(record, dict) or record.get("error") or record.get("cancelled"):
        return False
    if not record.get("audit") or not record.get("synthesis"):
        return False
    return any(h.get("passages") for h in record.get("hops") or [])


def find_saved_run(question: str, mode: str) -> str | None:
    """Id of the newest saved run for this exact question and mode, if any."""
    best = None
    if RUNS_DIR.is_dir():
        for p in RUNS_DIR.glob("*.json"):
            try:
                r = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            if (isinstance(r, dict) and r.get("question") == question and r.get("mode") == mode
                    and not r.get("followup_of") and _is_replayable(r)):
                key = r.get("saved_at") or ""
                if best is None or key > best[0]:
                    best = (key, r.get("run_id", p.stem))
    return best[1] if best else None


def list_runs() -> list[dict]:
    out = []
    if RUNS_DIR.is_dir():
        for p in RUNS_DIR.glob("*.json"):
            try:
                r = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            if not _is_replayable(r):
                continue
            audit = r.get("audit") or {}
            if _public_demo() and r.get("question") not in FEATURED_QUESTIONS:
                continue  # on a public host, strangers' questions are never listed for others
            out.append({
                "run_id": r.get("run_id", p.stem),
                "question": r.get("question"),
                "mode": r.get("mode"),
                "grade": audit.get("grade"),
                "score": (audit.get("scores") or {}).get("evidence_support_score"),
                "saved_at": r.get("saved_at"),
            })
    out.sort(key=lambda x: x.get("saved_at") or "", reverse=True)
    return out


# --------------------------------------------------------------------------
# SSE plumbing
# --------------------------------------------------------------------------

_DONE = object()


def sse(event: dict) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"


def _sse_response(gen) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


def _drain(q: "queue.Queue", workers_alive):
    """Yield SSE strings from q until the sentinel arrives; keep-alive when idle."""
    finished = 0
    expected = workers_alive
    while finished < expected:
        try:
            item = q.get(timeout=KEEPALIVE_SECONDS)
        except queue.Empty:
            yield ": keep-alive\n\n"
            continue
        if item is _DONE:
            finished += 1
            continue
        yield sse(item)


GENERIC_ERROR = "The research service is not available right now."
_PROVIDER = re.compile(r"claude|haiku|anthropic|credit-key|oauth|api[ _-]?key|credential|"
                       r"sign-in|\bmodel\b|\bllm|\.config|bearer|token", re.I)


def friendly_error(message: str) -> str:
    """Turn an internal exception string into plain words for the browser.
    Nothing about the provider, model or credentials is ever returned."""
    m = message or ""
    if "LLMOffline" in m:
        return ("This demo is running without internet, so only questions that were "
                "already saved can be replayed. Try one of the saved runs, or start the "
                "server online.")
    if "Cancelled" in m:
        return "The run was stopped."
    if "rate limited" in m:
        return "The research service is busy. Wait a minute and try again."
    if "could not reach" in m:
        return "Could not reach the research service. Check the internet connection."
    if "LLMRefusal" in m:
        return "The research service could not answer this request."
    if not m or _PROVIDER.search(m) or "status 4" in m or "status 5" in m:
        return GENERIC_ERROR
    return m


def _clean_params(q: str, hops) -> tuple[str, int, str | None]:
    q = (q or "").strip()
    if not q:
        return q, 0, "Type a question first."
    if len(q) > MAX_QUESTION_CHARS:
        return q, 0, f"Questions are limited to {MAX_QUESTION_CHARS} characters."
    try:
        h = int(hops)
    except (TypeError, ValueError):
        h = 4
    return q, max(1, min(h, 6)), None


# At most this many agent runs at once. Compare mode uses two.
MAX_CONCURRENT_RUNS = 4
_RUN_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)
BUSY_MESSAGE = "The server is busy with other runs. Wait a moment and try again."


def _acquire_slots(n: int) -> bool:
    got = 0
    for _ in range(n):
        if _RUN_SLOTS.acquire(blocking=False):
            got += 1
        else:
            for _ in range(got):
                _RUN_SLOTS.release()
            return False
    return True


def _agent_worker(question: str, mode: str, hops: int, llm, q: "queue.Queue", lane: str | None,
                  cancel: "threading.Event | None" = None, extra: dict | None = None) -> None:
    """Run one agent in the current thread, pushing events onto q.

    The caller must already hold one run slot; it is released here."""
    run_id = make_run_id(question, mode)

    held: list = []

    def emit(ev: dict) -> None:
        ev = dict(ev)
        if ev.get("type") == "done":
            # Held back until we know whether the run was kept; see below.
            if lane:
                ev["lane"] = lane
            held.append(ev)
            return
        if ev.get("type") == "error":
            ev["message"] = friendly_error(ev.get("message", ""))
        if lane:
            ev["lane"] = lane
        q.put(ev)

    try:
        from ouroboros import agent
        cfg = agent.AgentConfig(mode=mode, hops=hops)
        record = agent.run(question, cfg, llm, emit=emit, cancel=cancel)
        saved = False
        try:
            # Failed, stopped or evidence-free runs are not worth replaying.
            if _is_replayable(record):
                usage = getattr(llm, "usage", {}) or {}
                replay = usage.get("calls", 0) > 0 and usage.get("calls") == usage.get("cached_calls")
                prior = find_saved_run(question, mode) if (replay and not extra) else None
                if prior:
                    run_id = prior  # a pure replay reuses the saved run instead of adding a copy
                else:
                    save_run(run_id, {**record, **(extra or {})})
                saved = True
        except Exception as e:  # saving must not break the stream
            emit({"type": "error", "message": "This run finished but could not be saved."})
        no_evidence = not any(h.get("passages") for h in (record or {}).get("hops") or [])
        if is_offline() and not saved and no_evidence:
            ev = {"type": "error", "message": friendly_error("LLMOffline")}
            if lane:
                ev["lane"] = lane
            q.put(ev)
        else:
            for ev in held:
                if saved:
                    ev["run_id"] = run_id
                q.put(ev)
        q.put({"_record": record, "lane": lane})
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        ev = {"type": "error", "message": friendly_error(msg[:400])}
        if lane:
            ev["lane"] = lane
        q.put(ev)
        q.put({"_record": None, "lane": lane})
    finally:
        _RUN_SLOTS.release()
        q.put(_DONE)


def load_prev_run(prev: str) -> dict | None:
    """Load a saved run by id. The id must look like a saved run file name."""
    if not isinstance(prev, str) or not _RUN_ID.match(prev):
        return None
    p = RUNS_DIR / f"{prev}.json"
    try:
        if p.resolve().parent != RUNS_DIR.resolve() or not p.is_file():
            return None
        rec = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


@app.get("/api/research/stream")
def research_stream(q: str = "", mode: str = "guarded", hops: str = "4", prev: str = ""):
    question, n_hops, err = _clean_params(q, hops)
    if mode not in ("guarded", "standard"):
        err = err or "Mode must be guarded or standard."
    prev = (prev or "").strip()
    prev_rec = None
    if prev and not err:
        prev_rec = load_prev_run(prev)  # unknown id: treat it as a plain new question

    def gen():
        nonlocal question
        if err:
            yield sse({"type": "error", "message": err})
            return
        try:
            llm = make_llm()
        except Exception:
            yield sse({"type": "error", "message": GENERIC_ERROR})
            return
        extra = None
        if prev_rec is not None:
            prev_q = str(prev_rec.get("question") or "")
            if question.strip().lower() != prev_q.strip().lower():
                original = question
                try:
                    from ouroboros import chat
                    prev_a = str((prev_rec.get("synthesis") or {}).get("answer") or "")
                    question = chat.rewrite_followup(llm, prev_q, prev_a, original)
                except Exception:
                    question = original  # fall back to the raw follow-up text
                yield sse({"type": "rewrite", "question": question, "original": original})
                extra = {"followup_of": prev, "original_text": original}
        if not _acquire_slots(1):
            yield sse({"type": "error", "message": BUSY_MESSAGE})
            return
        qu: queue.Queue = queue.Queue()
        cancel = threading.Event()
        threading.Thread(target=_agent_worker,
                         args=(question, mode, n_hops, llm, qu, None, cancel, extra),
                         daemon=True).start()
        try:
            for chunk in _drain(_filter_records(qu), 1):
                yield chunk
        finally:
            cancel.set()  # the viewer left (or we finished): stop any remaining model calls

    return _sse_response(gen())


class _filter_records:
    """Queue wrapper that hides internal record messages from the SSE drain."""

    def __init__(self, q: "queue.Queue", sink: dict | None = None):
        self.q, self.sink = q, sink

    def get(self, timeout=None):
        while True:
            item = self.q.get(timeout=timeout)
            if isinstance(item, dict) and "_record" in item:
                if self.sink is not None:
                    self.sink[item.get("lane")] = item["_record"]
                continue
            return item


@app.get("/api/compare/stream")
def compare_stream(q: str = "", hops: str = "4"):
    question, n_hops, err = _clean_params(q, hops)

    def gen():
        if err:
            yield sse({"type": "error", "message": err})
            return
        try:
            base = make_llm()
        except Exception as e:
            yield sse({"type": "error", "message": GENERIC_ERROR})
            return
        if not _acquire_slots(2):
            yield sse({"type": "error", "message": BUSY_MESSAGE})
            return
        qu: queue.Queue = queue.Queue()
        records: dict = {}
        cancel = threading.Event()
        # One fork per lane: same cache and client, but each lane counts only its own calls.
        lane_llms = {lane: base.fork() for lane in ("standard", "guarded")}
        for lane in ("standard", "guarded"):
            threading.Thread(target=_agent_worker,
                             args=(question, lane, n_hops, lane_llms[lane], qu, lane, cancel),
                             daemon=True).start()
        try:
            for chunk in _drain(_filter_records(qu, records), 2):
                yield chunk
        finally:
            cancel.set()
        summary = {}
        try:
            from ouroboros import live_metrics
            for lane, rec in records.items():
                if rec:
                    summary[lane] = live_metrics.run_summary(rec)
        except Exception as e:
            yield sse({"type": "error", "message": "The comparison summary could not be built."})
        total = {k: sum(l.usage.get(k, 0) for l in lane_llms.values())
                 for k in ("calls", "cached_calls", "input_tokens", "output_tokens")}
        total["cost_usd"] = round(sum(l.usage.get("cost_usd", 0.0) for l in lane_llms.values()), 6)
        yield sse({"type": "compare_done", "summary": summary, "usage": total})

    return _sse_response(gen())


# --------------------------------------------------------------------------
# JSON endpoints
# --------------------------------------------------------------------------

def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def _json_body(request: Request) -> dict | None:
    try:
        body = await request.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


@app.post("/api/audit")
async def api_audit(request: Request):
    body = await _json_body(request)
    if body is None:
        return _err("Send a JSON body with question and answer.")
    question = str(body.get("question") or "").strip()
    answer = str(body.get("answer") or "").strip()
    model = str(body.get("model_name") or "Other")[:40]
    if not question or not answer:
        return _err("Both a question and an answer are needed.")
    if len(answer) > MAX_ANSWER_CHARS or len(question) > MAX_QUESTION_CHARS:
        return _err("That text is too long to audit.")

    def work():
        from ouroboros import audit
        from ouroboros.rag import EvidencePool
        llm = make_llm()
        report = audit.audit_answer(question, answer, EvidencePool(), llm, fetch_more=True)
        # SPEC 4: the response is the audit report itself, plus bookkeeping keys.
        return {**report, "model_name": model, "question": question, "usage": dict(llm.usage)}

    try:
        from starlette.concurrency import run_in_threadpool
        out = await run_in_threadpool(work)
        claims = out.get("claims") or []
        if claims and all("verification call failed" in str(c.get("note", "")) for c in claims):
            msg = friendly_error("LLMOffline") if is_offline() else \
                "The check could not be completed. Please try again."
            return _err(msg, 502)
        return out
    except Exception as e:
        return _err(friendly_error(f"Audit failed: {type(e).__name__}: {e}"[:400]), 502)


@app.post("/api/plain")
async def api_plain(request: Request):
    body = await _json_body(request)
    if body is None:
        return _err("Send a JSON body with a question.")
    question = str(body.get("question") or "").strip()
    if not question or len(question) > MAX_QUESTION_CHARS:
        return _err("Type a question first.")

    def work():
        from ouroboros import audit
        from ouroboros.rag import EvidencePool
        llm = make_llm()
        plain = audit.plain_answer(question, llm)
        report = audit.audit_answer(question, plain.get("answer", ""), EvidencePool(), llm,
                                    fetch_more=True, stated_confidence=plain.get("confidence"))
        # SPEC 4: plain_answer fields (answer, confidence) plus its audit.
        return {**plain, "question": question, "audit": report, "usage": dict(llm.usage)}

    try:
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(work)
    except Exception as e:
        return _err(friendly_error(f"Plain answer failed: {type(e).__name__}: {e}"[:400]), 502)


@app.get("/api/health")
def health():
    offline = is_offline()
    return {"ok": True, "offline": offline,
            "ready": bool(offline or credentials_kind() != "none")}


@app.get("/api/runs")
def runs():
    return list_runs()


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str):
    if not _RUN_ID.match(run_id):
        return _err("Run not found.", 404)
    p = RUNS_DIR / f"{run_id}.json"
    if not p.is_file():
        return _err("Run not found.", 404)
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return _err("Run file is unreadable.", 500)


@app.get("/api/benchmark")
def benchmark():
    return build_benchmark()


@app.get("/api/code")
def code(path: str = ""):
    if _public_demo():
        return _err("Not found.", 404)
    real = resolve_code_path(path)
    if real is None:
        return _err("Not found.", 404)
    return {"path": path, "text": real.read_text(encoding="utf-8", errors="replace")}


@app.get("/api/code/list")
def code_list():
    if _public_demo():
        return {"files": []}
    return {"files": list_code_files()}


@app.get("/api/tests")
def tests_report():
    p = OUTPUTS_DIR / "test_report.json"
    if not p.is_file():
        return _err("No test report yet.", 404)
    try:
        rep = json.loads(p.read_text())
    except (OSError, ValueError):
        return _err("Test report is unreadable.", 500)
    # Tests about the service connection are internal; keep them out of the browser.
    hide = re.compile(r"credential|oauth|token|llm|provider|api_key|bearer|secret", re.I)
    def neutral(t):
        if isinstance(t, dict) and hide.search(json.dumps(t)):
            return {**t, "id": "SVC-" + format(zlib.crc32(str(t.get("id")).encode()) % 1000, "03d"), "input": "Service connection check", "remarks": "Service connection"}
        return t
    for key in ("automated", "defects"):
        if isinstance(rep.get(key), list):
            rep[key] = [neutral(t) for t in rep[key]]
    return rep


def _page(name: str):
    p = STATIC_DIR / name
    if not p.is_file():
        return JSONResponse({"error": "UI not built yet"}, status_code=404)
    return FileResponse(p, headers={"Cache-Control": "no-cache"})


@app.get("/")
def landing():
    """The standalone landing page (its own document, no app shell)."""
    return _page("landing.html")


@app.get("/app")
@app.get("/app/")
def index():
    """The chat app. Hash routes (#/ask, #/r/<id>, #/audit ...) are handled in the browser."""
    return _page("index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    p = STATIC_DIR / "img" / "favicon-64.png"
    if not p.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
