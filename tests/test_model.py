from datetime import timedelta
import unittest

import numpy as np

from ltfj.model import adjusted, alarm_threshold, calibrate_offset, scores, split_indices
from ltfj.predict import probability


class ModelTests(unittest.TestCase):
    def test_split_purges_target_crossing_boundary(self):
        rows=[dict(time="2023-12-30T20:00Z",target_end="2023-12-30T23:00Z"),
              dict(time="2023-12-30T22:00Z",target_end="2023-12-31T01:00Z"),
              dict(time="2024-01-01T00:00Z",target_end="2024-01-01T03:00Z")]
        np.testing.assert_array_equal(split_indices(rows,"2021-01-01","2024-01-01",24),[0])

    def test_offset_matches_validation_rate_and_preserves_ranking(self):
        y=np.array([0,0,0,1])
        p=np.array([.001,.01,.02,.10])
        out=adjusted(p,calibrate_offset(y,p))
        self.assertAlmostEqual(float(out.mean()),.25)
        self.assertTrue(np.all(np.diff(out)>0))

    def test_alarm_goal_and_false_alarm_denominator(self):
        y=np.array([0,1,0,1,1]);p=np.array([.01,.04,.08,.1,.2])
        threshold=alarm_threshold(y,p,.7)
        metric=scores(y,p,threshold)
        self.assertGreaterEqual(metric["recall"],.7)
        self.assertAlmostEqual(metric["false_alarm_ratio"],1/4)

    def test_portable_prediction_imputes_and_marks_missing(self):
        parameters=dict(columns=["x"],imputation=[2.0],missing_indicator_indices=[0],
                        mean=[1.0,0],scale=[2.0,1],coefficients=[2.0,-1.0],
                        intercept=0.0,calibration_offset=0.0)
        self.assertAlmostEqual(probability({"x":""},parameters),.5)
        self.assertAlmostEqual(probability({"x":"3"},parameters),1/(1+np.exp(-2)))


if __name__ == "__main__":
    unittest.main()
