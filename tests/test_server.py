"""Server tests. httpx is not installed in the venv, so fastapi.testclient is
unavailable when it is missing; the handlers and helpers are then called directly."""
import asyncio
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from app import server


def collect(resp) -> list:
    async def go():
        return [c async for c in resp.body_iterator]
    return asyncio.run(go())


def events(chunks) -> list:
    return [json.loads(c[6:]) for c in chunks if c.startswith("data: ")]


class TestAllowList(unittest.TestCase):
    def test_allowed(self):
        for p in ["ouroboros/metric.py", "ouroboros/retrieval.py",
                  "run_experiment.py", "run_diagnostic.py"]:
            self.assertIsNotNone(server.resolve_code_path(p), p)

    def test_service_files_hidden(self):
        for p in ["app/server.py", "tests/test_server.py", "tests/test_chat.py",
                  "ouroboros/llm.py", "tests/test_llm.py"]:
            self.assertIsNone(server.resolve_code_path(p), p)
        for rel in server.list_code_files():
            text = (server.ROOT / rel).read_text(errors="replace").lower()
            for word in ("anthropic", "haiku", "credit-key", "oauth"):
                self.assertNotIn(word, text, f"{rel} mentions {word}")

    def test_rejected(self):
        bad = ["../etc/passwd", "ouroboros/../README.md", "/etc/passwd", "README.md",
               "ouroboros/sub/x.py", "ouroboros/metric.py\x00.txt", "ouroboros\\metric.py",
               "ouroboros/.env", "app/static/app.js", "outputs/traces.jsonl", "", "ouroboros/",
               "ouroboros/nonexistent_file.py", "..", "%2e%2e/secret", "app/runs/x.json",
               "ouroboros//metric.py"]
        for p in bad:
            self.assertIsNone(server.resolve_code_path(p), repr(p))

    def test_symlink_and_case_alias_rejected(self):
        link = server.ROOT / "ouroboros" / "zz_link_test.py"
        try:
            link.symlink_to(server.ROOT / "requirements.txt")
        except OSError:
            self.skipTest("cannot create symlink")
        try:
            self.assertIsNone(server.resolve_code_path("ouroboros/zz_link_test.py"))
        finally:
            link.unlink()
        self.assertIsNone(server.resolve_code_path("ouroboros/LLM.py"))

    def test_endpoint_status(self):
        self.assertEqual(server.code("ouroboros/metric.py")["path"], "ouroboros/metric.py")
        self.assertEqual(server.code("../README.md").status_code, 404)

    def test_public_demo_serves_no_code(self):
        with mock.patch.dict("os.environ", {"PUBLIC_DEMO": "1"}):
            self.assertEqual(server.code("ouroboros/metric.py").status_code, 404)
            self.assertEqual(server.code_list(), {"files": []})
        self.assertEqual(server.code("ouroboros/metric.py")["path"], "ouroboros/metric.py")

    def test_public_quota(self):
        with mock.patch.object(server, "PUBLIC_PER_IP_HOUR", 3), \
                mock.patch.object(server, "PUBLIC_PER_DAY", 5), \
                mock.patch.dict(server._limit_hits, clear=True), \
                mock.patch.dict(server._limit_day, {"day": "", "count": 0}):
            self.assertTrue(server._take_public_quota("1.1.1.1"))
            self.assertTrue(server._take_public_quota("1.1.1.1", 2))
            self.assertFalse(server._take_public_quota("1.1.1.1"))      # hourly limit per visitor
            self.assertTrue(server._take_public_quota("2.2.2.2", 2))
            self.assertFalse(server._take_public_quota("3.3.3.3"))      # daily limit for the site

    def test_public_runs_featured_only(self):
        with mock.patch.dict("os.environ", {"PUBLIC_DEMO": "1"}):
            for r in server.list_runs():
                self.assertIn(r["question"], server.FEATURED_QUESTIONS)

    def test_symlink_escape(self):
        link = server.ROOT / "tests" / "zz_link_tmp.py"
        try:
            link.symlink_to("/etc/hosts")
        except OSError:
            self.skipTest("symlinks unavailable")
        try:
            self.assertIsNone(server.resolve_code_path("tests/zz_link_tmp.py"))
        finally:
            link.unlink()


class TestBenchmark(unittest.TestCase):
    def test_parse_phase1(self):
        with tempfile.TemporaryDirectory() as d:
            t, g = Path(d) / "t.jsonl", Path(d) / "d.json"
            rows = [
                {"question_id": "a", "type": "contested", "arm": "drift", "hop": 1, "query": "q",
                 "baqd": 0.0, "support": 1, "oppose": 3, "skew": -0.5, "balance_loss": 0.5},
                {"question_id": "a", "type": "contested", "arm": "drift", "hop": 2, "query": "q2",
                 "baqd": 0.2, "support": 2, "oppose": 2, "skew": 0.0, "balance_loss": 0.0},
                {"question_id": "a", "type": "contested", "arm": "neutral", "hop": 2, "query": "q3",
                 "baqd": 0.0, "support": 4, "oppose": 0, "skew": 1.0, "balance_loss": 1.0},
            ]
            t.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
            g.write_text(json.dumps([{"id": "a", "neutral": 0.5, "drift_hop3": 0.0,
                                      "oracle_support": 1.0, "oracle_oppose": -1.0,
                                      "shared_vocab_ratio": 0.1}]))
            out = server.parse_phase1(t, g)
        self.assertEqual(out["n_trace_rows"], 3)
        self.assertEqual(out["n_questions"], 1)
        self.assertEqual(out["hops"], 2)
        self.assertEqual(out["final_hop_mean_balance_loss"]["drift"]["contested"], 0.0)
        self.assertEqual(out["final_hop_mean_balance_loss"]["neutral"]["contested"], 1.0)
        self.assertEqual(out["diagnostic"]["n"], 1)
        self.assertEqual([h["hop"] for h in out["questions"][0]["arms"]["drift"]], [1, 2])

    def test_missing_files(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(server.parse_phase1(Path(d) / "x", Path(d) / "y"))

    def test_real_outputs(self):
        b = server.build_benchmark()
        if (server.OUTPUTS_DIR / "traces.jsonl").is_file():
            self.assertEqual(b["phase1"]["n_trace_rows"], 48)


class TestHealthAndRuns(unittest.TestCase):
    def test_health_no_token(self):
        h = server.health()
        self.assertEqual(set(h), {"ok", "offline", "ready"})
        self.assertTrue(h["ok"])
        blob = json.dumps(h).lower()
        for bad in ("claude", "haiku", "anthropic", "oauth", "token", "credit-key", "model"):
            self.assertNotIn(bad, blob)

    def test_offline_is_ready(self):
        with mock.patch.dict("os.environ", {"OFFLINE": "1"}):
            self.assertTrue(server.health()["ready"])

    def test_offline_env(self):
        with mock.patch.dict("os.environ", {"OFFLINE": "1"}):
            self.assertTrue(server.health()["offline"])
        with mock.patch.dict("os.environ", {"OFFLINE": "0"}):
            self.assertFalse(server.health()["offline"])

    def test_run_id_and_bad_run_lookup(self):
        rid = server.make_run_id("Is Nuclear power good?!", "guarded")
        self.assertRegex(rid, r"^is-nuclear-power-good-guarded-[0-9a-f]{6}$")
        self.assertEqual(server.run_detail("../../etc/passwd").status_code, 404)
        self.assertEqual(server.run_detail("nope").status_code, 404)

    def test_save_and_list(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(server, "RUNS_DIR", Path(d)):
            server.save_run("r1-guarded-abc123", {"question": "q", "mode": "guarded",
                            "synthesis": {"answer": "a"}, "hops": [{"hop": 1, "passages": [{"pid": "p#0"}]}],
                            "audit": {"grade": "Partly supported", "scores": {"evidence_support_score": 60.0}}})
            server.save_run("bad-guarded-abc123", {"question": "q2", "mode": "guarded", "error": "LLMOffline",
                            "audit": {"grade": "x"}, "synthesis": {"answer": "a"}, "hops": []})
            self.assertEqual(len(server.list_runs()), 1)
            lst = server.list_runs()
            self.assertEqual(lst[0]["grade"], "Partly supported")
            self.assertEqual(lst[0]["score"], 60.0)
            self.assertEqual(server.run_detail("r1-guarded-abc123")["question"], "q")


def fake_modules():
    agent = types.ModuleType("ouroboros.agent")

    class Cfg:
        def __init__(self, **kw):
            self.__dict__.update(kw)
    agent.AgentConfig = Cfg

    def run(question, cfg, llm, emit=lambda e: None, cancel=None):
        emit({"type": "start", "question": question, "mode": cfg.mode})
        emit({"type": "done", "usage": {}, "seconds": 0.0})
        return {"question": question, "mode": cfg.mode, "audit": {"grade": "x"},
                "synthesis": {"answer": "a"}, "hops": [{"hop": 1, "passages": [{"pid": "p#0"}]}]}
    agent.run = run
    llm = types.ModuleType("ouroboros.llm")

    class LLM:
        def __init__(self, cache_dir="", offline=False):
            self.usage = {}

        def fork(self):
            return LLM()
    llm.LLM = LLM
    llm.MODEL = "fake"
    lm = types.ModuleType("ouroboros.live_metrics")
    lm.run_summary = lambda rec: {"mode": rec["mode"]}
    return {"ouroboros.agent": agent, "ouroboros.llm": llm, "ouroboros.live_metrics": lm}


def patched(mods):
    """Swap the fake modules into sys.modules and onto the package, since
    `from ouroboros import agent` reads the package attribute once the real
    submodule has been imported by another test."""
    import contextlib
    import ouroboros

    @contextlib.contextmanager
    def cm():
        with mock.patch.dict(sys.modules, mods), contextlib.ExitStack() as st:
            for name, mod in mods.items():
                st.enter_context(mock.patch.object(ouroboros, name.split(".")[-1], mod, create=True))
            yield
    return cm()


class TestStreams(unittest.TestCase):
    def test_validation_errors_are_events(self):
        ev = events(collect(server.research_stream(q="", mode="guarded", hops=4)))
        self.assertEqual(ev[0]["type"], "error")
        ev = events(collect(server.research_stream(q="x", mode="weird", hops=4)))
        self.assertEqual(ev[0]["type"], "error")

    def test_research_stream_and_save(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(server, "RUNS_DIR", Path(d)), \
                patched(fake_modules()):
            ev = events(collect(server.research_stream(q="Is tea good?", mode="standard", hops=2)))
            self.assertEqual([e["type"] for e in ev], ["start", "done"])
            self.assertTrue(ev[-1]["run_id"].startswith("is-tea-good-standard-"))
            self.assertEqual(len(list(Path(d).glob("*.json"))), 1)

    def test_compare_stream_lanes(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(server, "RUNS_DIR", Path(d)), \
                patched(fake_modules()):
            ev = events(collect(server.compare_stream(q="Is tea good?", hops=2)))
            lanes = {e.get("lane") for e in ev if e["type"] == "start"}
            self.assertEqual(lanes, {"standard", "guarded"})
            self.assertEqual(ev[-1]["type"], "compare_done")
            self.assertEqual(set(ev[-1]["summary"]), {"standard", "guarded"})

    def test_failed_run_is_not_saved(self):
        mods = fake_modules()
        mods["ouroboros.agent"].run = lambda q, cfg, llm, emit=None, cancel=None: {
            "question": q, "mode": cfg.mode, "hops": [], "error": "LLMOffline: x", "audit": None}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(server, "RUNS_DIR", Path(d)), \
                patched(mods):
            collect(server.research_stream(q="x", mode="guarded", hops=2))
            self.assertEqual(list(Path(d).glob("*.json")), [])

    def test_friendly_error(self):
        self.assertIn("not available right now", server.friendly_error("LLMOffline: offline and not cached (tag='read')"))
        self.assertEqual(server.friendly_error("plain"), "plain")

    def test_busy_when_slots_full(self):
        held = [server._RUN_SLOTS.acquire(blocking=False) for _ in range(server.MAX_CONCURRENT_RUNS)]
        try:
            with patched(fake_modules()):
                ev = events(collect(server.research_stream(q="x", mode="guarded", hops=2)))
            self.assertEqual(ev[0]["type"], "error")
            self.assertIn("busy", ev[0]["message"])
        finally:
            for ok in held:
                if ok:
                    server._RUN_SLOTS.release()

    def test_agent_crash_becomes_error_event(self):
        mods = fake_modules()
        def boom(*a, **k):
            raise RuntimeError("boom")
        mods["ouroboros.agent"].run = boom
        with tempfile.TemporaryDirectory() as d, mock.patch.object(server, "RUNS_DIR", Path(d)), \
                patched(mods):
            ev = events(collect(server.research_stream(q="x", mode="guarded", hops=2)))
            self.assertEqual(ev[-1]["type"], "error")
            self.assertIn("boom", ev[-1]["message"])


class TestPages(unittest.TestCase):
    """The landing page is its own document at "/", the chat app lives at "/app"."""

    def body(self, resp) -> str:
        return Path(resp.path).read_text()

    def test_landing_is_standalone(self):
        resp = server.landing()
        self.assertEqual(Path(resp.path).name, "landing.html")
        html = self.body(resp)
        self.assertIn("<title>Ouroboros</title>", html)
        self.assertIn("landing.js", html)
        self.assertIn("landing.css", html)
        self.assertIn("favicon-32.png", html)
        self.assertIn("ouro-theme", html)
        for app_only in ("core.js", "thread.js", "pages.js", 'id="sidebar"'):
            self.assertNotIn(app_only, html)

    def test_app_is_the_chat_shell(self):
        for fn in (server.index,):
            resp = fn()
            self.assertEqual(Path(resp.path).name, "index.html")
            html = self.body(resp)
            self.assertIn("core.js", html)
            self.assertNotIn("landing.js", html)
            self.assertIn('href="/"', html)  # quiet About link back to the landing page

    def test_routes_registered(self):
        paths = {getattr(r, "path", None) for r in server.app.routes}
        for p in ("/", "/app", "/app/", "/favicon.ico"):
            self.assertIn(p, paths)

    def test_favicon(self):
        resp = server.favicon()
        self.assertEqual(resp.media_type, "image/png")
        self.assertTrue(Path(resp.path).is_file())

    def test_landing_has_no_internal_words(self):
        js = (server.STATIC_DIR / "js" / "landing.js").read_text()
        html = self.body(server.landing())
        for text in (js, html):
            self.assertNotIn("\u2014", text)  # no em dash
            self.assertNotIn("->", text)


if __name__ == "__main__":
    unittest.main()
