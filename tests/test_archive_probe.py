import unittest
from ltfj.archive_probe import gfs_url, validate_sample
from ltfj.error_audit import regimes


class ArchiveTests(unittest.TestCase):
    def test_reject_analysis_and_wrong_valid_time(self):
        with self.assertRaises(ValueError):
            gfs_url("2024010100", 0)
        with self.assertRaises(ValueError):
            validate_sample([{"time": "2024-01-01T00:00:00Z", "x[unit=K]": "1"}],
                            "2024010100", 6, ["x"])

    def test_missing_value_is_not_forecast(self):
        row = {"time": "2024-01-01T06:00:00Z", "x[unit=K]": "NaN"}
        with self.assertRaises(ValueError):
            validate_sample([row], "2024010100", 6, ["x"])
        row["x[unit=K]"] = "280"
        validate_sample([row], "2024010100", 6, ["x"])

    def test_unknown_conditions_are_not_dry_or_calm(self):
        row = dict(fog_mist="0", rain="0", spread_c="", ceiling_ft="",
                   ceiling_change_1h_ft="", wind_speed_kt="")
        groups = regimes(row)
        self.assertIn("spread_missing", groups)
        self.assertIn("wind_missing", groups)
        self.assertNotIn("spread_gt_2c", groups)
        self.assertNotIn("wind_le_5kt", groups)
