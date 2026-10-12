"""End to end invariants, and a regression test for a bug found during development.

The regression test pins a fix that was made after the first experiment run
produced noise. The encoder had been fitted separately on each question's eight
passages, so the inverse document frequency statistics were computed over a
corpus far too small to be meaningful. A retriever indexes the whole collection,
so the encoder must be fitted over the whole collection too.
"""

import json
import os
import unittest

from ouroboros.metric import balance_loss
from ouroboros.retrieval import Encoder, Retriever

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "spiral_bench_v0.json")
OUT = os.path.join(HERE, "outputs")


def load_bench():
    with open(DATA) as f:
        return json.load(f)


def full_corpus_texts(bench):
    texts = []
    for it in bench["questions"]:
        texts += [p["text"] for p in it["passages"]]
        texts += it["queries_drift"] + it["queries_neutral"] + [it["question"]]
    return texts


class TestRetrieverEdges(unittest.TestCase):
    """TC-35 to TC-37."""

    def setUp(self):
        self.bench = load_bench()
        self.enc = Encoder(full_corpus_texts(self.bench))
        self.item = self.bench["questions"][0]
        self.r = Retriever(self.item["passages"], self.enc)

    def test_tc35_k_of_zero_returns_empty_list(self):
        self.assertEqual(self.r.search(self.item["question"], k=0), [])

    def test_tc36_negative_k_returns_empty_list_not_whole_corpus(self):
        """A negative k must not silently slice from the end of the ranking."""
        self.assertEqual(self.r.search(self.item["question"], k=-1), [])

    def test_tc37_score_is_rounded_to_four_places(self):
        for h in self.r.search(self.item["question"], k=4):
            self.assertEqual(h["score"], round(h["score"], 4))


class TestEncoderRegression(unittest.TestCase):
    """TC-38: regression test for the per question encoder bug."""

    def test_tc38_encoder_must_be_fitted_on_the_whole_collection(self):
        """Fitting on one question's passages alone destroys the ranking signal.

        With a vocabulary built from eight passages, a query sharing real
        content words with a passage can score zero against it, because the
        words simply are not in the vocabulary. Fitting over the whole
        collection keeps those words and preserves the ranking.
        """
        bench = load_bench()
        item = next(i for i in bench["questions"] if i["id"] == "vitamin_d")
        probe = "savings from owning an electric car"   # vocabulary from another question

        narrow = Encoder([p["text"] for p in item["passages"]])
        wide = Encoder(full_corpus_texts(bench))

        narrow_vec = narrow.encode(probe)
        wide_vec = wide.encode(probe)

        self.assertEqual(float(narrow_vec.sum()), 0.0,
                         "a narrowly fitted encoder should lose this vocabulary entirely")
        self.assertGreater(float(wide_vec.sum()), 0.0,
                           "the collection wide encoder must retain it")


class TestExperimentInvariants(unittest.TestCase):
    """TC-39 to TC-42: properties the published numbers depend on."""

    @classmethod
    def setUpClass(cls):
        cls.traces_path = os.path.join(OUT, "traces.jsonl")
        cls.diag_path = os.path.join(OUT, "diagnostic.json")

    def test_tc39_trace_log_has_one_row_per_retrieval(self):
        with open(self.traces_path) as f:
            rows = [json.loads(l) for l in f]
        bench = load_bench()
        expected = len(bench["questions"]) * 2 * 3      # questions x arms x hops
        self.assertEqual(len(rows), expected)

    def test_tc40_hop_one_drift_score_is_zero_by_construction(self):
        """At hop 1 the query is the question and the belief is the question."""
        with open(self.traces_path) as f:
            rows = [json.loads(l) for l in f]
        for r in (r for r in rows if r["hop"] == 1):
            self.assertEqual(r["baqd"], 0.0, f"{r['question_id']} {r['arm']}")

    def test_tc41_settled_questions_cannot_lose_balance(self):
        with open(self.traces_path) as f:
            rows = [json.loads(l) for l in f]
        for r in (r for r in rows if r["type"] == "settled"):
            self.assertEqual(r["oppose"], 0)
            self.assertEqual(r["balance_loss"], 1.0)

    def test_tc42_oracle_spread_is_the_full_range(self):
        """The headline claim: query wording can reach both extremes."""
        with open(self.diag_path) as f:
            diag = json.load(f)
        for d in diag:
            self.assertEqual(d["oracle_support"], 1.0, d["id"])
            self.assertEqual(d["oracle_oppose"], -1.0, d["id"])


class TestBalanceHelper(unittest.TestCase):
    """TC-43."""

    def test_tc43_balance_loss_matches_manual_computation(self):
        self.assertAlmostEqual(balance_loss([1, 1, 1, -1]), 0.5, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
