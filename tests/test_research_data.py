from datetime import timedelta
import unittest

from ltfj.metar import parse
from ltfj.pipeline import build_rows, timestamp
from ltfj.research_data import asof, consensus, extract_raw


class ResearchDataTests(unittest.TestCase):
    def test_raw_formats(self):
        for text in ["MET040METAR COR LTFJ 010020Z 9999 BKN004=", "LTFJ 010020Z 9999 BKN004"]:
            self.assertIs(parse(extract_raw(text))["below_500"], True)
        self.assertIsNone(extract_raw("SYN07017063 11956"))

    def test_consensus_does_not_pick_conflicting_target(self):
        a = parse("LTFJ 010020Z 9999 BKN004")
        b = parse("LTFJ 010020Z 9999 BKN005")
        value, conflicts = consensus([a,b])
        self.assertIsNone(value["below_500"])
        self.assertIn("below_500", conflicts)

    def test_numeric_height_conflict_preserves_agreed_threshold(self):
        a = parse("LTFJ 010020Z 9999 BKN010")
        b = parse("LTFJ 010020Z 9999 BKN020")
        value, _ = consensus([a,b])
        self.assertIs(value["below_500"], False)
        self.assertIsNone(value["ceiling_ft"])

    def test_delayed_feature_cannot_see_recent_report(self):
        t = timestamp("2025-01-01T01:00Z")
        observations = [dict(time=t-timedelta(minutes=m), **parse(f"LTFJ 010000Z 9999 BKN{h}"))
                        for m,h in [(20,"010"),(5,"004")]]
        f,_=build_rows(observations,t,t+timedelta(minutes=30),delay_minutes=10)
        self.assertEqual(f[0]["ceiling_ft"],1000)
        self.assertIsNone(asof(observations,[o['time'] for o in observations],t-timedelta(hours=1)))


if __name__ == "__main__":
    unittest.main()
