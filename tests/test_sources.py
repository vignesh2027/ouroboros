"""Offline tests for ouroboros.sources. No network is used."""

import os
import tempfile
import time
import unittest
from unittest import mock

from ouroboros import sources
from ouroboros.sources import Document

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def make_doc(source="web", url="https://a.example/x", text="some evidence text"):
    return Document(sources.doc_id_for(url), source, "T", url, "a.example", text, 2020, {"k": 1})


class TestCleaning(unittest.TestCase):
    def test_strip_tags_and_entities(self):
        self.assertEqual(sources.strip_tags("The <b>fastest</b> bike &amp; more"), "The fastest bike & more")

    def test_clean_text_caps_and_collapses(self):
        out = sources.clean_text("word " * 5000, cap=100)
        self.assertLessEqual(len(out), 100)
        self.assertNotIn("  ", out)

    def test_html_to_text_removes_chrome(self):
        text = sources.html_to_text(fixture("page.html"))
        self.assertIn("Kawasaki Ninja H2", text)
        self.assertIn("differ between & reviewers", text)
        for junk in ("tracking", "navigation", "cookies", "late script", "Privacy policy",
                     "Related posts", "Share this article", "<", ">"):
            self.assertNotIn(junk, text)
        self.assertNotIn("Short.", text)

    def test_html_to_text_cap(self):
        big = "<p>" + ("This is a reasonably long sentence about motorcycles and speed. " * 400) + "</p>"
        self.assertLessEqual(len(sources.html_to_text(big)), sources.MAX_TEXT)

    def test_keywords_drop_stop_words(self):
        self.assertEqual(sources.keywords("What is the fastest bike in India?"), ["fastest", "bike", "India"])


class TestRedirects(unittest.TestCase):
    def test_unwrap_uddg(self):
        u = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.example.org%2Fbikes%3Fa%3D1%26b%3D2&rut=abc"
        self.assertEqual(sources.unwrap_ddg(u), "https://www.example.org/bikes?a=1&b=2")

    def test_ads_and_junk_rejected(self):
        self.assertIsNone(sources.unwrap_ddg("//duckduckgo.com/y.js?ad=1"))
        self.assertIsNone(sources.unwrap_ddg(""))
        self.assertIsNone(sources.unwrap_ddg("javascript:void(0)"))

    def test_direct_link_kept(self):
        self.assertEqual(sources.unwrap_ddg("https://direct.example.com/p"), "https://direct.example.com/p")

    def test_parse_ddg_fixture(self):
        res = sources.parse_ddg(fixture("ddg_results.html"))
        self.assertEqual(len(res), 2)  # the ad is dropped
        self.assertEqual(res[0]["url"], "https://www.example.org/bikes?a=1&b=2")
        self.assertEqual(res[0]["title"], "Fastest bikes in India")
        self.assertTrue(res[0]["snippet"].startswith("The Kawasaki Ninja H2 is the fastest"))
        self.assertNotIn("<b>", res[0]["snippet"])
        self.assertEqual(res[1]["url"], "https://direct.example.com/page")


class TestParsers(unittest.TestCase):
    def test_arxiv(self):
        docs = sources.parse_arxiv(fixture("arxiv.xml"))
        self.assertEqual(len(docs), 1)  # entry with empty summary skipped
        d = docs[0]
        self.assertEqual(d.source, "arxiv")
        self.assertEqual(d.title, "Self-confirming retrieval loops in agents")
        self.assertTrue(d.text.startswith("Self-confirming retrieval loops in agents. We study"))
        self.assertEqual(d.year, 2024)
        self.assertEqual(d.meta["authors"], ["A. Author", "B. Writer"])
        self.assertEqual(d.domain, "arxiv.org")

    def test_pubmed(self):
        docs = sources.parse_pubmed(fixture("pubmed.xml"))
        self.assertEqual(len(docs), 1)  # no abstract, skipped
        d = docs[0]
        self.assertEqual(d.url, "https://pubmed.ncbi.nlm.nih.gov/12345/")
        self.assertEqual(d.year, 2019)
        self.assertIn("weight loss: a trial.", d.text)
        self.assertIn("Background: Fasting is popular. Results: Weight fell by 3 kg & fat mass", d.text)
        self.assertNotIn("<i>", d.text)

    def test_openalex_abstract_rebuild(self):
        inv = {"fasting": [1], "Intermittent": [0], "works": [2]}
        self.assertEqual(sources._openalex_abstract(inv), "Intermittent fasting works")
        self.assertEqual(sources._openalex_abstract(None), "")

    def test_doc_id_stable(self):
        self.assertEqual(sources.doc_id_for("https://x.y/z"), sources.doc_id_for("https://x.y/z"))
        self.assertEqual(len(sources.doc_id_for("https://x.y/z")), 12)


class TestSearchAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def fake(self, calls, docs_by_source):
        def mk(name):
            def f(q, n):
                calls.append(name)
                if name == "boom":
                    raise RuntimeError("nope")
                return docs_by_source.get(name, [])
            return f
        return {s: mk(s) for s in list(docs_by_source) + ["boom"]}

    def test_cache_hit_avoids_second_fetch(self):
        calls = []
        fakes = self.fake(calls, {"wikipedia": [make_doc("wikipedia", "https://w/1")]})
        with mock.patch.dict(sources.FETCHERS, fakes, clear=True):
            a = sources.search_all("Q one", 3, ["wikipedia"], self.tmp)
            b = sources.search_all("  q  ONE ", 3, ["wikipedia"], self.tmp)  # normalised key
        self.assertEqual(calls, ["wikipedia"])
        self.assertEqual([d.url for d in a], [d.url for d in b])
        self.assertIsInstance(b[0], Document)

    def test_offline_miss_is_empty_and_never_fetches(self):
        calls = []
        with mock.patch.dict(sources.FETCHERS, self.fake(calls, {"wikipedia": [make_doc()]}), clear=True):
            self.assertEqual(sources.search_all("q", 3, ["wikipedia"], self.tmp, offline=True), [])
        self.assertEqual(calls, [])

    def test_offline_reads_cache(self):
        calls = []
        with mock.patch.dict(sources.FETCHERS, self.fake(calls, {"wikipedia": [make_doc("wikipedia")]}), clear=True):
            sources.search_all("q", 3, ["wikipedia"], self.tmp)
            out = sources.search_all("q", 3, ["wikipedia"], self.tmp, offline=True)
        self.assertEqual(len(out), 1)

    def test_failing_fetcher_isolated_and_not_cached(self):
        calls = []
        fakes = self.fake(calls, {"wikipedia": [make_doc("wikipedia", "https://w/1")]})
        with mock.patch.dict(sources.FETCHERS, fakes, clear=True):
            out = sources.search_all("q", 3, ["boom", "wikipedia"], self.tmp)
            sources.search_all("q", 3, ["boom"], self.tmp)
        self.assertEqual([d.source for d in out], ["wikipedia"])
        self.assertEqual(calls.count("boom"), 2)  # failure was retried, not cached

    def test_empty_result_not_cached(self):
        calls = []
        with mock.patch.dict(sources.FETCHERS, self.fake(calls, {"wikipedia": []}), clear=True):
            sources.search_all("q", 3, ["wikipedia"], self.tmp)
            sources.search_all("q", 3, ["wikipedia"], self.tmp)
        self.assertEqual(calls, ["wikipedia", "wikipedia"])

    def test_dedupe_and_per_source_cap(self):
        same = make_doc("web", "https://dup/1")
        fakes = {
            "wikipedia": lambda q, n: [make_doc("wikipedia", f"https://w/{i}") for i in range(5)],
            "web": lambda q, n: [same],
            "arxiv": lambda q, n: [same],
        }
        with mock.patch.dict(sources.FETCHERS, fakes, clear=True):
            out = sources.search_all("q", 2, ["wikipedia", "web", "arxiv"], self.tmp)
        self.assertEqual(len(out), 3)  # 2 wiki + 1 deduped
        self.assertEqual(sorted({d.source for d in out}), ["web", "wikipedia"])

    def test_timeout_drops_slow_source(self):
        def slow(q, n):
            time.sleep(1.0)
            return [make_doc("web", "https://slow/1")]
        fakes = {"wikipedia": lambda q, n: [make_doc("wikipedia", "https://w/1")], "web": slow}
        with mock.patch.object(sources, "FETCH_TIMEOUT", 0.2), mock.patch.dict(sources.FETCHERS, fakes, clear=True):
            t = time.time()
            out = sources.search_all("q", 2, ["wikipedia", "web"], self.tmp)
        self.assertLess(time.time() - t, 0.9)
        self.assertEqual([d.source for d in out], ["wikipedia"])

    def test_unknown_source_and_blank_query(self):
        self.assertEqual(sources.search_all("q", 2, ["nope"], self.tmp), [])
        self.assertEqual(sources.search_all("   ", 2, None, self.tmp), [])

    def test_default_sources(self):
        self.assertEqual(sources.default_sources("x"), ["wikipedia", "openalex", "arxiv", "pubmed", "web"])


if __name__ == "__main__":
    unittest.main()
