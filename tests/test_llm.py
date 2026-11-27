import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from ouroboros import llm as llm_mod
from ouroboros.llm import LLM, LLMError, LLMOffline, LLMRefusal, MODEL, cache_key
from tests.fakes import FakeLLM

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}},
          "required": ["a"], "additionalProperties": False}


def fake_resp(text, stop="end_turn", i=1000, o=100):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=i, output_tokens=o),
    )


class Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.kwargs = []
        self.messages = self

    def create(self, **kw):
        self.kwargs.append(kw)
        return self.responses.pop(0)


class LLMTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def make(self, responses, offline=False):
        m = LLM(cache_dir=self.tmp.name, offline=offline)
        m._client = Client(responses)
        return m

    def test_cache_key_stable_and_sensitive(self):
        k = cache_key("s", "u", SCHEMA, "low")
        self.assertEqual(k, cache_key("s", "u", dict(reversed(list(SCHEMA.items()))), "low"))
        self.assertNotEqual(k, cache_key("s", "u2", SCHEMA, "low"))
        self.assertNotEqual(k, cache_key("s", "u", SCHEMA, "high"))
        self.assertEqual(len(k), 64)

    def test_call_then_cache_hit(self):
        m = self.make([fake_resp('{"a": "x"}')])
        self.assertEqual(m.json("s", "u", SCHEMA), {"a": "x"})
        self.assertEqual(m.json("s", "u", SCHEMA), {"a": "x"})
        self.assertEqual(m.usage["calls"], 2)
        self.assertEqual(m.usage["cached_calls"], 1)
        self.assertEqual(m.usage["input_tokens"], 1000)
        self.assertAlmostEqual(m.usage["cost_usd"], 1000 * 0.1e-6 + 100 * 0.5e-6)
        self.assertEqual(len(m._client.kwargs), 1)

    def test_request_shape(self):
        m = self.make([fake_resp('{"a": "x"}')])
        m.json("sys", "usr", SCHEMA, effort="low")
        kw = m._client.kwargs[0]
        self.assertEqual(kw["model"], MODEL)
        self.assertEqual(kw["output_config"]["effort"], "low")
        self.assertEqual(kw["output_config"]["format"]["type"], "json_schema")
        for banned in ("temperature", "top_p", "top_k", "thinking"):
            self.assertNotIn(banned, kw)

    def test_offline_miss_raises_and_hit_works(self):
        m = self.make([], offline=True)
        with self.assertRaises(LLMOffline):
            m.json("s", "u", SCHEMA)
        online = self.make([fake_resp('{"a": "y"}')])
        online.json("s", "u", SCHEMA)
        off = LLM(cache_dir=self.tmp.name, offline=True)
        self.assertEqual(off.json("s", "u", SCHEMA), {"a": "y"})
        self.assertEqual(off.usage["cached_calls"], 1)
        self.assertEqual(off.usage["cost_usd"], 0.0)

    def test_refusal(self):
        m = self.make([fake_resp("", stop="refusal")])
        with self.assertRaises(LLMRefusal):
            m.json("s", "u", SCHEMA)
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_max_tokens_retries_once_with_double(self):
        m = self.make([fake_resp('{"a"', stop="max_tokens"), fake_resp('{"a": "z"}')])
        self.assertEqual(m.json("s", "u", SCHEMA, max_tokens=100), {"a": "z"})
        self.assertEqual([k["max_tokens"] for k in m._client.kwargs], [100, 200])
        self.assertEqual(m.usage["input_tokens"], 2000)

    def test_max_tokens_twice_fails(self):
        m = self.make([fake_resp("{", stop="max_tokens"), fake_resp("{", stop="max_tokens")])
        with self.assertRaises(LLMError):
            m.json("s", "u", SCHEMA)

    def test_text_cached_separately_from_json(self):
        m = self.make([fake_resp("hello"), fake_resp('{"a": "x"}')])
        self.assertEqual(m.text("s", "u"), "hello")
        self.assertEqual(m.text("s", "u"), "hello")
        self.assertEqual(m.json("s", "u", SCHEMA), {"a": "x"})
        self.assertEqual(len(m._client.kwargs), 2)
        self.assertNotIn("format", m._client.kwargs[0]["output_config"])

    def test_api_errors_become_llmerror(self):
        import anthropic
        m = self.make([])
        req = mock.Mock()
        for exc in (
            anthropic.RateLimitError("x", response=mock.Mock(status_code=429, headers={}, request=req), body=None),
            anthropic.APIConnectionError(request=req),
        ):
            m._client = mock.Mock()
            m._client.messages.create.side_effect = exc
            with self.assertRaises(LLMError):
                m.json("s", "u", SCHEMA)

    def test_credential_kind_never_returns_secret(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret-value"}):
            self.assertEqual(llm_mod.credential_kind(), "api_key")
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        env["ANTHROPIC_AUTH_TOKEN"] = "secret-value"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(llm_mod.credential_kind(), "oauth_token")

    def test_oauth_client_construction(self):
        env = {"ANTHROPIC_AUTH_TOKEN": "tok"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("anthropic.Anthropic") as A:
            llm_mod._build_client()
        A.assert_called_once_with(auth_token="tok", api_key=None,
                                  default_headers={"anthropic-beta": "oauth-2025-04-20"})


class FakeLLMTest(unittest.TestCase):
    def test_canned_by_tag_and_records(self):
        f = FakeLLM({"read": {"x": 1}, "seq": [{"n": 1}, {"n": 2}],
                     "fn": lambda s, u, sc: {"echo": u}})
        self.assertEqual(f.json("s", "u", {}, tag="read"), {"x": 1})
        self.assertEqual(f.json("s", "u", {}, tag="seq"), {"n": 1})
        self.assertEqual(f.json("s", "u", {}, tag="seq"), {"n": 2})
        self.assertEqual(f.json("s", "u", {}, tag="seq"), {"n": 2})
        self.assertEqual(f.json("s", "hi", {}, tag="fn"), {"echo": "hi"})
        self.assertEqual(f.tags(), ["read", "seq", "seq", "seq", "fn"])
        with self.assertRaises(KeyError):
            f.json("s", "u", {}, tag="nope")


if __name__ == "__main__":
    unittest.main()
