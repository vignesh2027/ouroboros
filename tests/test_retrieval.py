"""Tests for the encoder and the retriever.

These probe the behaviour the experiment depends on: that ranking is
deterministic, that k is respected, and that out of vocabulary text does not
crash the pipeline.
"""

import unittest

from ouroboros.retrieval import Encoder, Retriever

CORPUS = [
    {"stance": 1, "text": "electric cars reduce fuel spending and save money over five years"},
    {"stance": 1, "text": "maintenance costs fall because electric drivetrains have fewer parts"},
    {"stance": -1, "text": "insurance premiums are higher for electric vehicles than petrol cars"},
    {"stance": -1, "text": "battery replacement outside warranty is a significant expense"},
]
FIT = [p["text"] for p in CORPUS] + [
    "is an electric car cheaper to own than a petrol car",
    "savings from owning an electric car",
]


class TestEncoder(unittest.TestCase):
    """TC-15 to TC-18."""

    def setUp(self):
        self.enc = Encoder(FIT)

    def test_tc15_encoding_is_deterministic(self):
        a = self.enc.encode("electric cars save money")
        b = self.enc.encode("electric cars save money")
        self.assertTrue((a == b).all())

    def test_tc16_out_of_vocabulary_text_gives_zero_vector(self):
        v = self.enc.encode("zzzz qqqq xxxx")
        self.assertEqual(float(v.sum()), 0.0)

    def test_tc17_empty_string_does_not_crash(self):
        v = self.enc.encode("")
        self.assertEqual(float(v.sum()), 0.0)

    def test_tc18_encode_many_matches_encode_one(self):
        texts = ["electric cars save money", "battery replacement expense"]
        many = self.enc.encode_many(texts)
        for i, t in enumerate(texts):
            self.assertTrue((many[i] == self.enc.encode(t)).all())


class TestRetriever(unittest.TestCase):
    """TC-19 to TC-24."""

    def setUp(self):
        self.enc = Encoder(FIT)
        self.r = Retriever(CORPUS, self.enc)

    def test_tc19_returns_exactly_k_results(self):
        self.assertEqual(len(self.r.search("electric car cost", k=2)), 2)
        self.assertEqual(len(self.r.search("electric car cost", k=4)), 4)

    def test_tc20_k_larger_than_corpus_returns_whole_corpus(self):
        hits = self.r.search("electric car cost", k=99)
        self.assertEqual(len(hits), len(CORPUS))

    def test_tc21_ranking_is_deterministic(self):
        a = [h["text"] for h in self.r.search("electric car savings", k=4)]
        b = [h["text"] for h in self.r.search("electric car savings", k=4)]
        self.assertEqual(a, b)

    def test_tc22_scores_are_in_descending_order(self):
        hits = self.r.search("electric car savings", k=4)
        scores = [h["score"] for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_tc23_every_hit_carries_a_stance(self):
        for h in self.r.search("electric car", k=4):
            self.assertIn(h["stance"], (1, -1))

    def test_tc24_out_of_vocabulary_query_still_returns_k_results(self):
        hits = self.r.search("zzzz qqqq", k=3)
        self.assertEqual(len(hits), 3)

    def test_tc25_leading_query_outranks_opposing_passages(self):
        """A query using only supporting vocabulary should surface supporting text first."""
        hits = self.r.search("savings money fuel spending", k=1)
        self.assertEqual(hits[0]["stance"], 1)

    def test_tc26_retriever_does_not_mutate_the_corpus(self):
        before = [dict(p) for p in CORPUS]
        self.r.search("electric car", k=4)
        self.assertEqual(CORPUS, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
