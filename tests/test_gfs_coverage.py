import unittest
from ltfj.gfs_coverage import select_cycle, forecast_bracket
from ltfj.pipeline import timestamp
from ltfj.gfs_profile_check import missing_variables


class AvailabilityTests(unittest.TestCase):
    def test_http_success_does_not_imply_complete_profile(self):
        missing = missing_variables(["Temperature_isobaric", "Geopotential_height_isobaric"])
        self.assertIn("Relative_humidity_isobaric", missing)
        self.assertEqual(len(missing), 3)

    def test_cycle_is_not_available_at_initialization(self):
        cycle = timestamp("2024-01-01T06:00Z")
        older = timestamp("2024-01-01T00:00Z")
        self.assertEqual(select_cycle(cycle, [older, cycle]), older)
        self.assertEqual(select_cycle(timestamp("2024-01-01T12:00Z"), [older, cycle]), cycle)

    def test_stale_missing_and_future_cycles_are_not_used(self):
        origin = timestamp("2024-01-02T00:00Z")
        self.assertIsNone(select_cycle(origin, [timestamp("2024-01-01T00:00Z"),
                                                timestamp("2024-01-02T06:00Z")]))
        self.assertIsNone(select_cycle(origin, []))

    def test_target_bracket_uses_forecast_leads(self):
        cycle = timestamp("2024-01-01T00:00Z")
        self.assertEqual(forecast_bracket(timestamp("2024-01-01T06:30Z"), cycle), (9, 12))
        self.assertEqual(forecast_bracket(timestamp("2024-01-01T06:00Z"), cycle), (9, 9))
        with self.assertRaises(ValueError):
            forecast_bracket(cycle, timestamp("2024-01-01T06:00Z"))
