import unittest
from ltfj.gfs_features import at_origin, FIELDS
from ltfj.pipeline import timestamp


class JoinTests(unittest.TestCase):
    def test_interpolation_uses_one_available_cycle(self):
        cycle = "2024-01-01T00:00:00Z"
        records = {(cycle, lead): {f: float(lead) for f in FIELDS} for lead in [6,9,12]}
        result = at_origin(timestamp("2024-01-01T06:30Z"), records)
        self.assertEqual(result["gfs_cycle"], cycle)
        self.assertAlmostEqual(result[f"gfs_{FIELDS[0]}_current"], 6.5)
        self.assertAlmostEqual(result[f"gfs_{FIELDS[0]}_change_3h"], 3.)

    def test_missing_old_cycle_cannot_be_filled_from_new_cycle(self):
        records = {("2024-01-01T06:00:00Z", lead): {f: 1. for f in FIELDS} for lead in [0,3,6,9]}
        result = at_origin(timestamp("2024-01-01T06:30Z"), records)
        self.assertEqual(result["gfs_status"], "missing_required_forecast")
        self.assertFalse(any(k.endswith("_current") for k in result))
