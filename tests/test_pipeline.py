import unittest
from datetime import timedelta

from ltfj.metar import parse
from ltfj.pipeline import (build_rows, load_observations, read_csv, target, timestamp)


T = timestamp("2025-01-01T00:00:00Z")


def metar(sky):
    return f"LTFJ 010000Z 06005KT 7000 {sky} 04/02 Q1033"


def obs(minutes, sky="BKN010"):
    return dict(time=T + timedelta(minutes=minutes), **parse(metar(sky)))


class MetarTests(unittest.TestCase):
    def test_threshold_and_lowest_layer(self):
        for sky, height, low in [("BKN005", 500, False), ("BKN004", 400, True),
                                 ("SCT002 BKN012 OVC008", 800, False),
                                 ("VV002", 200, True), ("VV000", 0, True)]:
            with self.subTest(sky=sky):
                result = parse(metar(sky))
                self.assertEqual(result["ceiling_ft"], height)
                self.assertIs(result["below_500"], low)

    def test_no_ceiling_is_not_numeric(self):
        for sky in ["CAVOK", "NSC", "NCD", "SKC", "CLR", "FEW002 SCT004"]:
            with self.subTest(sky=sky):
                result = parse(metar(sky))
                self.assertIsNone(result["ceiling_ft"])
                self.assertIs(result["below_500"], False)

    def test_missing_and_malformed_are_unknown(self):
        for sky in ["", "VV///", "BKN///", "//////", "BKN04", "OVC010 BKN///",
                    "CAVOK BKN004"]:
            with self.subTest(sky=sky):
                self.assertIsNone(parse(metar(sky))["below_500"])
        self.assertIsNone(parse("LTFJ 010000Z NIL")["below_500"])
        self.assertIsNone(parse("garbage")["below_500"])

    def test_known_low_with_unknown_layer(self):
        result = parse(metar("BKN004 OVC///"))
        self.assertIs(result["below_500"], True)
        self.assertIsNone(result["ceiling_ft"])

    def test_other_missing_fields_do_not_invalidate_ceiling(self):
        result = parse("LTFJ 010000Z /////KT //// NSC 10/09 Q1021")
        self.assertIs(result["below_500"], False)
        self.assertIsNone(result["visibility_m"])
        self.assertIsNone(result["wind_speed_kt"])

    def test_missing_header_is_unknown(self):
        self.assertIsNone(parse("LTFJ BKN004")["below_500"])

    def test_trends_and_remarks_are_not_observations(self):
        for suffix in ["TEMPO BKN002", "BECMG VV001", "RMK BKN001 24025KT",
                       "NOSIG RMK BKN001"]:
            result = parse(metar("BKN020") + " " + suffix)
            self.assertEqual(result["ceiling_ft"], 2000)
            self.assertEqual(result["wind_speed_kt"], 5)

    def test_temperature_visibility_and_weather(self):
        result = parse("SPECI LTFJ 010000Z VRB03G12KT 0400 FZFG VV002 M02/M03 Q1002")
        self.assertEqual(result["spread_c"], 1)
        self.assertEqual(result["visibility_m"], 400)
        self.assertEqual(result["weather"], "FZFG")
        self.assertIsNone(result["wind_direction_deg"])
        self.assertEqual(result["wind_gust_kt"], 12)


class LabelTests(unittest.TestCase):
    def label(self, current=None, future=None, end=None):
        return target(obs(0) if current is None else current,
                      [obs(x) for x in range(30, 181, 30)] if future is None else future,
                      T, end or T + timedelta(days=1))

    def test_full_negative(self):
        self.assertEqual(self.label(), (0, "no_observed_event"))

    def test_event_at_horizon(self):
        self.assertEqual(self.label(future=[obs(180, "BKN004")]), (1, "event"))

    def test_missing_report_prevents_negative(self):
        self.assertEqual(self.label(future=[obs(30), obs(90), obs(120), obs(150), obs(180)]),
                         (None, "coverage_gap"))

    def test_unknown_future_prevents_negative(self):
        self.assertEqual(self.label(future=[obs(30, "VV///")]), (None, "unknown_future"))

    def test_already_low_and_unknown_current(self):
        self.assertEqual(self.label(current=obs(0, "BKN004")),
                         (None, "already_below_threshold"))
        self.assertEqual(self.label(current=obs(0, "VV///")), (None, "unknown_current"))

    def test_stale_current(self):
        self.assertEqual(self.label(current=obs(-36)), (None, "missing_current"))

    def test_incomplete_tail(self):
        self.assertEqual(self.label(end=T + timedelta(hours=3)),
                         (None, "incomplete_horizon"))
        self.assertEqual(self.label(future=[obs(60, "BKN002")], end=T + timedelta(hours=2)),
                         (1, "event"))

    def test_grid_and_no_future_feature_leakage(self):
        data = [obs(-10), obs(20), obs(181, "BKN002")]
        features, labels = build_rows(data, T, T + timedelta(hours=4))
        self.assertEqual(len(features), 8)
        self.assertEqual(features[0]["ceiling_ft"], 1000)
        self.assertEqual(features[0]["observation_age_minutes"], 10)
        self.assertIsNone(labels[0]["below_500_within_3h"])
        self.assertEqual(labels[1]["below_500_within_3h"], 1)

    def test_event_at_current_time_is_not_new_event(self):
        _, labels = build_rows([obs(0, "BKN002"), obs(30)], T, T + timedelta(hours=1))
        self.assertEqual(labels[0]["label_status"], "already_below_threshold")


class SourceTests(unittest.TestCase):
    def test_bad_response(self):
        with self.assertRaises(ValueError):
            read_csv("<html>Service unavailable</html>")

    def test_duplicates_and_conflicts(self):
        row = dict(station="LTFJ", valid="2025-01-01 00:00", metar=metar("BKN010"))
        observations, counts = load_observations([row, row])
        self.assertEqual(counts["exact_duplicates"], 1)
        self.assertEqual(len(observations), 1)
        observations, counts = load_observations([row, dict(row, metar=metar("BKN002"))])
        self.assertEqual(counts["conflicting_timestamps"], 1)
        self.assertIsNone(observations[0]["below_500"])

    def test_reject_other_station(self):
        with self.assertRaises(ValueError):
            load_observations([dict(station="LTBA", valid="2025-01-01", metar="M")])

    def test_timestamp_mismatch_is_unknown(self):
        observations, counts = load_observations([
            dict(station="LTFJ", valid="2025-01-01 00:30", metar=metar("BKN002"))])
        self.assertIsNone(observations[0]["below_500"])
        self.assertEqual(counts["timestamp_mismatch_rows"], 1)


if __name__ == "__main__":
    unittest.main()
