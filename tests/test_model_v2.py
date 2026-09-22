"""Guard against accidental future-label features or random validation."""
import json
from pathlib import Path
import unittest

from ltfj.model import split_indices
from ltfj.model_v2 import candidate


class ChronologyTests(unittest.TestCase):
    def test_all_selection_outcomes_precede_calibration(self):
        protocol = json.loads(Path("research-protocol-v2.json").read_text())
        for start, boundary, end in protocol["selection_folds"]:
            self.assertLess(start, boundary)
            self.assertLess(boundary, end)
            self.assertLessEqual(end, protocol["calibration"][0])
            rows = [dict(time=boundary + "T00:00Z", target_end=boundary + "T03:00Z")]
            self.assertEqual(len(split_indices(rows, start, boundary, 24)), 0)

    def test_candidates_have_no_target_inputs_or_random_early_stopping(self):
        protocol = json.loads(Path("research-protocol-v2.json").read_text())
        for name in protocol["candidates"]:
            model, columns = candidate(name)
            self.assertFalse(set(columns) & {"below_500_within_3h", "target_end", "label_status"})
            if name.startswith("boost"):
                self.assertFalse(model.early_stopping)


if __name__ == "__main__":
    unittest.main()
