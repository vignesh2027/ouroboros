"""Regression tests for the second review round."""

import re
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from ouroboros import agent, audit
from ouroboros.agent import AgentConfig, Cancelled
from ouroboros.llm import LLM
from ouroboros.rag import EvidencePool, Passage
from ouroboros import sources
from tests.test_agent import FakeSearch, make_llm, read_fn, run_agent, QUESTION
from tests.test_llm import Client, fake_resp, SCHEMA


class LLMSingleFlight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_concurrent_identical_calls_make_one_request(self):
        m = LLM(cache_dir=self.tmp.name)
        calls = []

        class Slow(Client):
            def create(self, **kw):
                calls.append(1)
                time.sleep(0.15)
                return super().create(**kw)
        m._client = Slow([fake_resp('{"a": "x"}'), fake_resp('{"a": "y"}')])
        out = []
        ts = [threading.Thread(target=lambda: out.append(m.json("s", "u", SCHEMA))) for _ in range(2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(calls), 1)
        self.assertEqual(out[0], out[1])

    def test_fork_has_its_own_usage_and_shares_cache(self):
        m = LLM(cache_dir=self.tmp.name)
        m._client = Client([fake_resp('{"a": "x"}')])
        f = m.fork()
        f.json("s", "u", SCHEMA)
        self.assertEqual(f.usage["calls"], 1)
        self.assertEqual(m.usage["calls"], 0)
        m.json("s", "u", SCHEMA)
        self.assertEqual(m.usage["cached_calls"], 1)

    def test_malformed_cache_is_a_miss(self):
        m = LLM(cache_dir=self.tmp.name)
        m._client = Client([fake_resp('{"a": "x"}')])
        from ouroboros.llm import cache_key
        with open(m._path(cache_key("s", "u", SCHEMA, "low")), "w") as fh:
            fh.write("[1, 2]")
        self.assertEqual(m.json("s", "u", SCHEMA), {"a": "x"})
        self.assertEqual(m.usage["cached_calls"], 0)


class AgentFixes(unittest.TestCase):
    def test_neutrals_chosen_by_retrieval_score(self):
        seen, captured = {}, {}
        orig = EvidencePool.search

        def spy(self, *a, **kw):
            out = orig(self, *a, **kw)
            for p in out:
                if "pids" not in captured:
                    seen[p.pid] = p.score
            return out

        def synth(s, u, sc):
            captured["pids"] = re.findall(r'pid="([^"]+)"', u)
            return {"answer": "x", "confidence": 50, "one_line": "y"}
        llm = make_llm(read_fn(lambda i, p: "neutral"), synthesis=synth)
        with mock.patch.object(EvidencePool, "search", spy):
            run_agent(llm, AgentConfig(mode="standard", hops=2, k=4))
        self.assertEqual(len(captured["pids"]), agent.NEUTRAL_IN_SYNTHESIS)
        best = sorted(seen, key=lambda p: (-seen[p], p))[:agent.NEUTRAL_IN_SYNTHESIS]
        self.assertEqual(set(captured["pids"]), set(best))

    def test_cancel_stops_the_run(self):
        ev = threading.Event()
        ev.set()
        events = []
        with mock.patch.object(agent, "search_all", FakeSearch()):
            rec = agent.run(QUESTION, AgentConfig(hops=3, k=4), make_llm(read_fn(lambda i, p: "supports")),
                            emit=events.append, cancel=ev)
        self.assertTrue(rec.get("cancelled"))
        self.assertEqual(events[-1]["type"], "error")


class DelimiterFixes(unittest.TestCase):
    def test_attributes_are_escaped(self):
        p = Passage(pid="a#0", doc_id="a", source="web", title="t", url="u",
                    domain='a.com"><x', year=None, text="body")
        out = audit.format_passages([p])
        self.assertNotIn('"><x', out)
        self.assertIn("&quot;&gt;&lt;x", out)

    def test_plain_domain_unchanged(self):
        p = Passage(pid="a#0", doc_id="a", source="web", title="t", url="u",
                    domain="doi.org/10.1016", year=None, text="body")
        self.assertIn('domain="doi.org/10.1016"', audit.format_passages([p]))


class SSRF(unittest.TestCase):
    def test_non_public_refused(self):
        for u in ("http://127.0.0.1:8000/api/runs", "http://localhost/x", "http://169.254.169.254/latest",
                  "http://10.0.0.5/", "ftp://example.com/", "http:///x"):
            self.assertFalse(sources.is_public_url(u), u)

    def test_http_refuses_private(self):
        with self.assertRaises(Exception):
            sources._http("http://127.0.0.1:9/", public_only=True)

    def test_public_ip_allowed(self):
        self.assertTrue(sources.is_public_url("http://8.8.8.8/"))


class ExperimentLimitation(unittest.TestCase):
    def test_flags_exhausted_corpus(self):
        import importlib.util, os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "experiments", "run_live_spiral.py")
        spec = importlib.util.spec_from_file_location("rls", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        def run(mode, pids):
            return {"qid": "q", "type": "contested", "mode": mode, "error": None,
                    "hops": [{"hop": 1, "pids": pids, "baqd": None},
                             {"hop": 2, "pids": [], "baqd": -0.1}]}
        same = [run("standard", ["a", "b"]), run("guarded", ["b", "a"])]
        self.assertIn("not informative", mod.design_limitation(same))
        diff = [run("standard", ["a", "b"]), run("guarded", ["a", "c"])]
        self.assertIsNone(mod.design_limitation(diff))
        self.assertEqual(mod.baqd_hops(same[0]), [])


if __name__ == "__main__":
    unittest.main()
