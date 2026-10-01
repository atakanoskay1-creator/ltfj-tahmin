import unittest

from ltfj.predict_gfs import state


class PredictGfsTests(unittest.TestCase):
    def test_current_state_guards(self):
        self.assertEqual(state({"below_500": "True", "observation_age_minutes": "0"}),
                         "already_below_threshold")
        self.assertEqual(state({"below_500": "", "observation_age_minutes": "0"}),
                         "insufficient_current_observation")
        self.assertEqual(state({"below_500": "False", "observation_age_minutes": "36"}),
                         "insufficient_current_observation")
        self.assertEqual(state({"below_500": "False", "observation_age_minutes": "10"}),
                         "research_estimate")


if __name__ == "__main__":
    unittest.main()
