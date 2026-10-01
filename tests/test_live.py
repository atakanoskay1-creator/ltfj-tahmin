import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ltfj.live import append_prediction, nomads_url, prediction_origin


class LiveTests(unittest.TestCase):
    def test_operational_grid_selection(self):
        utc = timezone.utc
        self.assertEqual(prediction_origin(datetime(2026, 10, 1, 10, 25, tzinfo=utc)),
                         datetime(2026, 10, 1, 10, 30, tzinfo=utc))
        self.assertEqual(prediction_origin(datetime(2026, 10, 1, 10, 15, tzinfo=utc)),
                         datetime(2026, 10, 1, 10, 0, tzinfo=utc))

    def test_nomads_request_is_exact_point_and_fields(self):
        url = nomads_url(datetime(2026, 10, 1, 0, tzinfo=timezone.utc), 9)
        for value in ["f009", "lev_850_mb=on", "lev_925_mb=on", "var_RH=on",
                      "leftlon=29.25", "rightlon=29.25", "toplat=41", "bottomlat=41"]:
            self.assertIn(value, url)

    def test_prediction_ledger_is_chained_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ledger.jsonl"
            first, created = append_prediction(path, {"prediction_time": "2026-10-01T10:30:00Z", "p": .1})
            self.assertTrue(created)
            second, created = append_prediction(path, {"prediction_time": "2026-10-01T11:00:00Z", "p": .2})
            self.assertTrue(created)
            self.assertEqual(second["previous_hash"], first["entry_hash"])
            saved = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(saved), 2)
            existing, created = append_prediction(path, {"prediction_time": "2026-10-01T11:00:00Z", "p": .3})
            self.assertFalse(created)
            self.assertEqual(existing["p"], .2)
            self.assertEqual(len(path.read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
