"""Offline tests for ouroboros.rag."""

import unittest
from dataclasses import dataclass, field

from ouroboros.rag import EvidencePool, Passage, chunk, tokenize


@dataclass
class Doc:
    """Same fields as ouroboros.sources.Document, so rag duck-types on it."""

    doc_id: str
    source: str
    title: str
    url: str
    domain: str
    text: str
    year: int | None = None
    meta: dict = field(default_factory=dict)


def sentence(i, n=12):
    return " ".join(f"Word{i}x{j}" for j in range(n - 1)) + f" end{i}."


def make_doc(doc_id, text, domain="example.org", title="T"):
    return Doc(doc_id, "web", title, f"https://{domain}/{doc_id}", domain, text, 2020)


class ChunkTests(unittest.TestCase):
    def test_sizes_and_ids(self):
        text = " ".join(sentence(i) for i in range(40))  # 480 words
        ps = chunk(make_doc("d1", text), max_words=60)
        self.assertGreater(len(ps), 1)
        for p in ps:
            self.assertLessEqual(len(p.text.split()), 75)  # 1.25 * max with tail merge
        self.assertEqual([p.pid for p in ps], [f"d1#{i}" for i in range(len(ps))])
        # no words lost or reordered
        self.assertEqual(" ".join(p.text for p in ps), text)

    def test_default_is_whole_sentences_in_range(self):
        text = " ".join(sentence(i, 20) for i in range(30))
        ps = chunk(make_doc("d2", text))
        for p in ps[:-1]:
            self.assertTrue(p.text.endswith("."))
            self.assertGreaterEqual(len(p.text.split()), 60)
            self.assertLessEqual(len(p.text.split()), 110)

    def test_long_sentence_is_split(self):
        text = " ".join(f"w{i}" for i in range(250)) + "."
        ps = chunk(make_doc("d3", text), max_words=100)
        self.assertEqual(len(ps), 3)
        self.assertTrue(all(len(p.text.split()) <= 100 for p in ps))

    def test_empty_and_metadata(self):
        self.assertEqual(chunk(make_doc("d4", "   ")), [])
        p = chunk(make_doc("d5", "One sentence here.", domain="a.org", title="Hello"))[0]
        self.assertEqual((p.doc_id, p.domain, p.title, p.year), ("d5", "a.org", "Hello", 2020))

    def test_bad_max_words(self):
        with self.assertRaises(ValueError):
            chunk(make_doc("d6", "x."), max_words=0)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.pool = EvidencePool()
        self.pool.add_documents(
            [
                make_doc("cat", "Cats are small carnivorous mammals. Cats purr and hunt mice.", "cats.org"),
                make_doc("dog", "Dogs are loyal domestic animals. Dogs bark and fetch sticks.", "dogs.org"),
                make_doc("bike", "The Kawasaki Ninja H2R is the fastest production motorcycle. "
                                 "Motorcycle top speed is measured in kilometres per hour.", "bikes.org"),
            ]
        )

    def test_bm25_ordering(self):
        res = self.pool.search("fastest motorcycle speed", k=3)
        self.assertEqual(res[0].doc_id, "bike")
        self.assertEqual(self.pool.search("cats purr", k=1)[0].doc_id, "cat")
        scores = [p.score for p in self.pool.search("cats dogs motorcycle", k=3, diversity=0)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_exclude(self):
        first = self.pool.search("cats purr", k=1)[0]
        res = self.pool.search("cats purr", k=5, exclude={first.pid})
        self.assertNotIn(first.pid, [p.pid for p in res])

    def test_no_overlap_returns_nothing(self):
        self.assertEqual(self.pool.search("quantum chromodynamics"), [])
        self.assertEqual(self.pool.search("the of and"), [])

    def test_k_and_empty_pool(self):
        self.assertEqual(self.pool.search("cats", k=0), [])
        self.assertEqual(EvidencePool().search("cats"), [])

    def test_lazy_refit_sees_new_documents(self):
        self.assertEqual(self.pool.search("submarine sonar"), [])
        n = self.pool.add_documents([make_doc("sub", "A submarine uses sonar to detect ships.", "navy.org")])
        self.assertEqual(n, 1)
        self.assertEqual(self.pool.search("submarine sonar", k=1)[0].doc_id, "sub")

    def test_duplicate_docs_skipped_and_get(self):
        before = len(self.pool)
        n = self.pool.add_documents([make_doc("cat", "Different text entirely.")])
        self.assertEqual((n, len(self.pool)), (0, before))
        self.assertIsInstance(self.pool.get("cat#0"), Passage)
        with self.assertRaises(KeyError):
            self.pool.get("nope#9")

    def test_search_does_not_mutate_pool(self):
        self.pool.search("cats", k=2)
        self.assertEqual(self.pool.get("cat#0").score, 0.0)


class DiversityTests(unittest.TestCase):
    def build(self):
        pool = EvidencePool()
        pool.add_documents(
            [
                make_doc("a1", "Intermittent fasting weight loss evidence strong.", "big.com"),
                make_doc("a2", "Intermittent fasting weight loss evidence strong again.", "big.com"),
                make_doc("b1", "Fasting and weight loss: some mixed evidence exists.", "other.org"),
            ]
        )
        return pool

    def test_same_domain_not_both_top2_with_diversity(self):
        pool = self.build()
        flat = pool.search("intermittent fasting weight loss evidence", k=2, diversity=0)
        self.assertEqual({p.domain for p in flat}, {"big.com"})  # the failure we guard against
        top2 = pool.search("intermittent fasting weight loss evidence", k=2, diversity=1)
        self.assertEqual({p.domain for p in top2}, {"big.com", "other.org"})

    def test_same_doc_chunks_spread(self):
        pool = EvidencePool(max_words=12)
        long_text = " ".join("Solar panels convert sunlight into power daily." for _ in range(6))
        pool.add_documents([make_doc("long", long_text, "x.org"),
                            make_doc("short", "Solar panels are cheap now.", "y.org")])
        res = pool.search("solar panels sunlight power", k=2, diversity=1)
        self.assertEqual({p.doc_id for p in res}, {"long", "short"})

    def test_diversity_zero_is_pure_score_order(self):
        pool = self.build()
        res = pool.search("intermittent fasting weight loss evidence", k=3, diversity=0)
        scores = [p.score for p in res]
        self.assertEqual(scores, sorted(scores, reverse=True))


class DeterminismTests(unittest.TestCase):
    def test_repeat_and_order_independent_ties(self):
        docs = [make_doc(f"d{i}", "identical text about tides and moons.", f"s{i}.org") for i in range(5)]
        runs = []
        for order in (docs, list(reversed(docs))):
            pool = EvidencePool()
            pool.add_documents(order)
            a = [p.pid for p in pool.search("tides moons", k=5)]
            b = [p.pid for p in pool.search("tides moons", k=5)]
            self.assertEqual(a, b)
            runs.append(a)
        self.assertEqual(runs[0], runs[1])  # tie-break on pid, not insertion order
        self.assertEqual(runs[0], sorted(runs[0]))

    def test_tokenize_drops_stop_words(self):
        self.assertEqual(tokenize("The Cat and the HAT"), ["cat", "hat"])


if __name__ == "__main__":
    unittest.main()
