"""Tests for the BAQD metric and the evidence balance measures.

Each test carries a TC id so the results map directly onto the test case
documentation table.
"""

import unittest

import numpy as np

from ouroboros.metric import cosine, baqd, evidence_skew, balance_loss


class TestCosine(unittest.TestCase):
    """TC-01 to TC-05: the similarity primitive."""

    def test_tc01_identical_vectors_give_one(self):
        v = np.array([1.0, 2.0, 3.0])
        self.assertAlmostEqual(cosine(v, v), 1.0, places=6)

    def test_tc02_orthogonal_vectors_give_zero(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        self.assertAlmostEqual(cosine(a, b), 0.0, places=6)

    def test_tc03_zero_vector_does_not_divide_by_zero(self):
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 2.0, 3.0])
        self.assertEqual(cosine(a, b), 0.0)

    def test_tc04_opposite_vectors_give_minus_one(self):
        a = np.array([1.0, 2.0])
        self.assertAlmostEqual(cosine(a, -a), -1.0, places=6)

    def test_tc05_result_stays_within_minus_one_and_one(self):
        rng = np.random.default_rng(0)
        for _ in range(200):
            a = rng.normal(size=12)
            b = rng.normal(size=12)
            s = cosine(a, b)
            self.assertGreaterEqual(s, -1.0000001)
            self.assertLessEqual(s, 1.0000001)


class TestBaqd(unittest.TestCase):
    """TC-06 to TC-09: the drift score itself."""

    def test_tc06_query_equal_to_question_gives_zero(self):
        q0 = np.array([1.0, 0.0, 0.0])
        belief = np.array([0.5, 0.5, 0.0])
        self.assertAlmostEqual(baqd(q0, belief, q0), 0.0, places=6)

    def test_tc07_query_aligned_with_belief_is_positive(self):
        question = np.array([1.0, 0.0])
        belief = np.array([0.0, 1.0])
        query = np.array([0.0, 1.0])          # written straight from the belief
        self.assertGreater(baqd(query, belief, question), 0.0)

    def test_tc08_query_away_from_belief_is_negative(self):
        question = np.array([0.0, 1.0])
        belief = np.array([0.0, 1.0])
        query = np.array([1.0, 0.0])          # deliberately disconfirming
        self.assertLess(baqd(query, belief, question), 0.0)

    def test_tc09_zero_belief_is_handled(self):
        q = np.array([1.0, 1.0])
        zero = np.array([0.0, 0.0])
        self.assertEqual(baqd(q, zero, q), 0.0)


class TestEvidenceBalance(unittest.TestCase):
    """TC-10 to TC-14: evidence skew and balance loss."""

    def test_tc10_all_supporting_gives_plus_one(self):
        self.assertEqual(evidence_skew([1, 1, 1, 1]), 1.0)

    def test_tc11_all_opposing_gives_minus_one(self):
        self.assertEqual(evidence_skew([-1, -1, -1, -1]), -1.0)

    def test_tc12_balanced_set_gives_zero(self):
        self.assertEqual(evidence_skew([1, 1, -1, -1]), 0.0)

    def test_tc13_empty_set_does_not_crash(self):
        self.assertEqual(evidence_skew([]), 0.0)
        self.assertEqual(balance_loss([]), 0.0)

    def test_tc14_balance_loss_is_never_negative(self):
        for stances in ([1, 1, 1], [-1, -1, -1], [1, -1], [1, 1, -1]):
            self.assertGreaterEqual(balance_loss(stances), 0.0)
            self.assertLessEqual(balance_loss(stances), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
