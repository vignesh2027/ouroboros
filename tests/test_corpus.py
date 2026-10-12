"""Integrity tests for SPIRAL-Bench.

The central claim of the experiment is that the corpus is balanced by
construction. These tests enforce that claim so it cannot quietly rot.
"""

import json
import os
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "spiral_bench_v0.json")


class TestCorpusIntegrity(unittest.TestCase):
    """TC-27 to TC-34."""

    @classmethod
    def setUpClass(cls):
        with open(DATA) as f:
            cls.bench = json.load(f)
        cls.items = cls.bench["questions"]

    def test_tc27_every_contested_question_is_balanced(self):
        for item in self.items:
            if item["type"] != "contested":
                continue
            sup = sum(1 for p in item["passages"] if p["stance"] > 0)
            opp = sum(1 for p in item["passages"] if p["stance"] < 0)
            self.assertEqual(sup, opp, f"{item['id']} is {sup} support vs {opp} oppose")

    def test_tc28_settled_questions_are_one_sided(self):
        for item in self.items:
            if item["type"] != "settled":
                continue
            opp = sum(1 for p in item["passages"] if p["stance"] < 0)
            self.assertEqual(opp, 0, f"{item['id']} should have no opposing passages")

    def test_tc29_stance_is_only_plus_or_minus_one(self):
        for item in self.items:
            for p in item["passages"]:
                self.assertIn(p["stance"], (1, -1), f"{item['id']} has stance {p['stance']}")

    def test_tc30_question_ids_are_unique(self):
        ids = [i["id"] for i in self.items]
        self.assertEqual(len(ids), len(set(ids)))

    def test_tc31_both_arms_have_the_same_number_of_hops(self):
        for item in self.items:
            self.assertEqual(len(item["queries_drift"]), len(item["queries_neutral"]),
                             f"{item['id']} arms differ in length")

    def test_tc32_first_query_of_each_arm_is_the_neutral_question(self):
        """Hop 1 must be identical in both arms, otherwise the comparison is unfair."""
        for item in self.items:
            self.assertEqual(item["queries_drift"][0], item["question"],
                             f"{item['id']} drift arm does not start neutral")
            self.assertEqual(item["queries_neutral"][0], item["question"],
                             f"{item['id']} neutral arm does not start neutral")

    def test_tc33_no_passage_text_is_duplicated(self):
        seen = {}
        for item in self.items:
            for p in item["passages"]:
                key = p["text"].strip().lower()
                self.assertNotIn(key, seen,
                                 f"duplicate passage in {item['id']} and {seen.get(key)}")
                seen[key] = item["id"]

    def test_tc34_no_query_is_empty(self):
        for item in self.items:
            for arm in ("queries_drift", "queries_neutral"):
                for q in item[arm]:
                    self.assertTrue(q.strip(), f"{item['id']} has an empty query in {arm}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
