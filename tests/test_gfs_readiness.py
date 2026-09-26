import unittest
from ltfj.gfs_readiness import audit, FEATURES


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.protocol = dict(coverage_years=[2021], assumed_publication_delay_hours=6,
            minimum_yearly_eligible_origin_coverage=.95, minimum_yearly_positive_origin_coverage=.95)
        self.labels = [dict(time="2021-01-01T06:00Z", below_500_within_3h="1")]
        self.features = [dict(time=self.labels[0]["time"], gfs_cycle="2021-01-01T00:00Z",
            gfs_status="available_under_assumption", **{f: "1" for f in FEATURES})]

    def test_complete_example_passes(self):
        self.assertTrue(audit(self.labels, self.features, self.protocol)["ready"])

    def test_future_cycle_or_nan_cannot_pass(self):
        self.features[0]["gfs_cycle"] = "2021-01-01T06:00Z"
        self.assertFalse(audit(self.labels, self.features, self.protocol)["ready"])
        self.features[0]["gfs_cycle"] = "2021-01-01T00:00Z"
        self.features[0][FEATURES[0]] = "nan"
        self.assertFalse(audit(self.labels, self.features, self.protocol)["ready"])

    def test_uncovered_positive_fails_even_if_overall_coverage_high(self):
        labels = [dict(time=f"2021-01-{d:02d}T06:00Z", below_500_within_3h=str(int(d==1)))
                  for d in range(1, 26)]
        features = [dict(self.features[0], time=r["time"], gfs_cycle=r["time"].replace("06:00", "00:00"))
                    for r in labels]
        features[0]["gfs_status"] = "missing_required_forecast"
        result = audit(labels, features, self.protocol)
        self.assertEqual(result["years"]["2021"]["coverage"], .96)
        self.assertFalse(result["ready"])

    def test_misalignment_is_rejected(self):
        with self.assertRaises(ValueError):
            audit(self.labels, [], self.protocol)
