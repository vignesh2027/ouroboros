import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import server
from ouroboros import chat
from tests.fakes import FakeLLM
from tests.test_server import collect, events, fake_modules, patched


class TestChat(unittest.TestCase):
    def test_rewrite_uses_followup_tag_and_delimiters(self):
        llm = FakeLLM({"followup": {"question": "  Does fasting help older adults? "}})
        out = chat.rewrite_followup(llm, "Is fasting good?", "x" * 5000, "what about older adults?")
        self.assertEqual(out, "Does fasting help older adults?")
        call = llm.calls[0]
        self.assertEqual(call["tag"], "followup")
        self.assertIn("<<<ANSWER", call["user"])
        self.assertLess(len(call["user"]), 2200)

    def test_empty_rewrite_raises(self):
        with self.assertRaises(ValueError):
            chat.rewrite_followup(FakeLLM({"followup": {"question": " "}}), "a", "b", "c")


class TestPrevAndStream(unittest.TestCase):
    def _runs(self, d):
        (Path(d) / "base-guarded-abc123.json").write_text(json.dumps(
            {"question": "Is fasting good?", "synthesis": {"answer": "Some."}}))

    def test_prev_validation(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(server, "RUNS_DIR", Path(d)):
            self._runs(d)
            self.assertIsNotNone(server.load_prev_run("base-guarded-abc123"))
            for bad in ("../x", "..", "a/b", "Base", "", "missing-run", "a" * 200):
                self.assertIsNone(server.load_prev_run(bad))

    def test_unknown_prev_runs_as_plain_question(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(server, "RUNS_DIR", Path(d)), \
                patched(fake_modules()):
            ev = events(collect(server.research_stream(q="more?", mode="guarded", hops=2, prev="../etc")))
            self.assertNotIn("error", [e["type"] for e in ev])
            self.assertEqual(ev[0]["type"], "start")

    def _run(self, llm_cls_patch):
        mods = fake_modules()
        seen = {}
        orig = mods["ouroboros.agent"].run

        def run(question, cfg, llm, emit=lambda e: None, cancel=None):
            seen["q"] = question
            return orig(question, cfg, llm, emit=emit, cancel=cancel)
        mods["ouroboros.agent"].run = run
        mods["ouroboros.llm"].LLM = llm_cls_patch
        with tempfile.TemporaryDirectory() as d, mock.patch.object(server, "RUNS_DIR", Path(d)), \
                patched(mods):
            self._runs(d)
            ev = events(collect(server.research_stream(
                q="what about older adults?", mode="guarded", hops=2, prev="base-guarded-abc123")))
            saved = [json.loads(p.read_text()) for p in Path(d).glob("*.json")
                     if p.name != "base-guarded-abc123.json"]
        return ev, seen, saved

    def test_rewrite_event_comes_first(self):
        fake = FakeLLM({"followup": {"question": "Is fasting safe for older adults?"}})

        class L:
            def __init__(self, cache_dir="", offline=False):
                self.usage = {}
                self.json = fake.json

            def fork(self):
                return L()
        ev, seen, saved = self._run(L)
        self.assertEqual([e["type"] for e in ev], ["rewrite", "start", "done"])
        self.assertEqual(ev[0]["question"], "Is fasting safe for older adults?")
        self.assertEqual(seen["q"], "Is fasting safe for older adults?")
        self.assertEqual(saved[0]["followup_of"], "base-guarded-abc123")
        self.assertEqual(saved[0]["original_text"], "what about older adults?")

    def test_rewrite_failure_falls_back(self):
        class L:
            def __init__(self, cache_dir="", offline=False):
                self.usage = {}

            def json(self, *a, **k):
                raise RuntimeError("LLMOffline: not cached")

            def fork(self):
                return L()
        ev, seen, saved = self._run(L)
        self.assertEqual(ev[0]["type"], "rewrite")
        self.assertEqual(seen["q"], "what about older adults?")
        self.assertEqual(ev[-1]["type"], "done")


class TestNoProviderLeaks(unittest.TestCase):
    def test_errors_are_generic(self):
        for raw in ("LLMError: no credentials found", "model API error, status 401",
                    "Claude haiku rejected the oauth token", "LLMError: model returned invalid JSON"):
            out = server.friendly_error(raw).lower()
            for bad in ("claude", "haiku", "anthropic", "oauth", "credential", "token", "api"):
                self.assertNotIn(bad, out)

    def test_llm_source_not_browsable(self):
        self.assertIsNone(server.resolve_code_path("ouroboros/llm.py"))
        self.assertNotIn("ouroboros/llm.py", server.list_code_files())
        self.assertIn("ouroboros/agent.py", server.list_code_files())


if __name__ == "__main__":
    unittest.main()
