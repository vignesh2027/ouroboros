import unittest

from ouroboros.live_metrics import calibration_gap, run_summary, source_diversity


class P:
    def __init__(self, domain, source):
        self.domain, self.source = domain, source


class SourceDiversityTest(unittest.TestCase):
    def test_dicts(self):
        d = source_diversity([
            {"domain": "a.org", "source": "web"},
            {"domain": "a.org", "source": "web"},
            {"domain": "b.org", "source": "arxiv"},
            {"domain": "c.org", "source": "web"},
        ])
        self.assertEqual(d["domains"], 3)
        self.assertEqual(d["sources"], 2)
        self.assertAlmostEqual(d["top_domain_share"], 0.5)

    def test_objects(self):
        d = source_diversity([P("a.org", "web"), P("b.org", "pubmed")])
        self.assertEqual((d["domains"], d["sources"]), (2, 2))
        self.assertAlmostEqual(d["top_domain_share"], 0.5)

    def test_empty(self):
        self.assertEqual(source_diversity([]),
                         {"domains": 0, "sources": 0, "top_domain_share": 0.0})


class CalibrationGapTest(unittest.TestCase):
    def test_values(self):
        self.assertEqual(calibration_gap(90, 40), 50.0)
        self.assertEqual(calibration_gap(30, 70), -40.0)
        self.assertEqual(calibration_gap(50, 50), 0.0)

    def test_missing(self):
        self.assertIsNone(calibration_gap(None, 50))
        self.assertIsNone(calibration_gap(50, None))


class RunSummaryTest(unittest.TestCase):
    def run_record(self):
        return {
            "hops": [
                {"hop": 1, "baqd": None, "skew": 0.5,
                 "passages": [{"domain": "a.org"}, {"domain": "b.org"}]},
                {"hop": 2, "baqd": 0.1, "skew": 0.2, "passages": [{"domain": "a.org"}]},
                {"hop": 3, "baqd": 0.3, "skew": -0.25, "passages": [{"domain": "c.org"}]},
            ],
            "cqi_events": [{"hop": 2}],
            "audit": {"scores": {"evidence_support_score": 62.5}},
        }

    def test_full(self):
        s = run_summary(self.run_record())
        self.assertAlmostEqual(s["mean_baqd"], 0.2)
        self.assertAlmostEqual(s["max_baqd"], 0.3)
        self.assertEqual(s["final_skew"], -0.25)
        self.assertEqual(s["cqi_count"], 1)
        self.assertEqual(s["domains_total"], 3)
        self.assertEqual(s["evidence_support_score"], 62.5)

    def test_hop1_null_excluded(self):
        r = {"hops": [{"hop": 1, "baqd": None, "skew": 0.0, "passages": []}]}
        s = run_summary(r)
        self.assertIsNone(s["mean_baqd"])
        self.assertIsNone(s["max_baqd"])
        self.assertIsNone(s["evidence_support_score"])
        self.assertEqual(s["cqi_count"], 0)

    def test_empty_run(self):
        s = run_summary({})
        self.assertIsNone(s["final_skew"])
        self.assertEqual(s["domains_total"], 0)


if __name__ == "__main__":
    unittest.main()
