import csv
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from ltfj.adequacy import compare_noaa, runs
from ltfj.metar import parse
from ltfj.pipeline import timestamp


class AdequacyTests(unittest.TestCase):
    def test_runs_split_on_recovery_and_gap(self):
        t = timestamp("2025-01-01")
        observations = [dict(time=t+timedelta(minutes=m),
                             **parse(f"LTFJ 010000Z 00000KT 9999 BKN{h} 10/09 Q1010"))
                        for m, h in [(0, "004"), (30, "003"), (60, "010"),
                                     (90, "002"), (150, "004")]]
        self.assertEqual([r["count"] for r in runs(observations)], [2, 1, 1])

    def test_noaa_special_changes_negative_label(self):
        raw = "METAR COR LTFJ 010020Z 00000KT 9999 BKN010 10/09 Q1010"
        observations = [dict(time=timestamp(f"2025-01-01T{h:02}:{m:02}"),
                             **parse(raw)) for h in range(5) for m in [20, 50]]
        fields = ["STATION", "DATE", "REPORT_TYPE", "CIG", "REM"]
        rows = [dict(STATION="17063099999", DATE="2025-01-01T00:20:00",
                     REPORT_TYPE="FM-15", CIG="00305,1,9,N", REM="MET070"+raw),
                dict(STATION="17063099999", DATE="2025-01-01T01:05:00",
                     REPORT_TYPE="FM-16", CIG="00122,1,9,N",
                     REM="MET070SPECI LTFJ 010105Z 00000KT 1000 BKN004 10/09 Q1010")]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"noaa.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            result = compare_noaa(path, observations)
        self.assertEqual(result["counts"]["matched_raw_ceiling_status"], 1)
        self.assertEqual(result["missing_from_iem_by_type"], {"FM-16": 1})
        sensitivity = result["augmentation_sensitivity"]
        self.assertEqual(sensitivity["added_low_reports"], 1)
        self.assertIn("2025-01-01T00:30:00Z", sensitivity["fixed_current_negative_to_positive_origins"])


if __name__ == "__main__":
    unittest.main()
