import unittest

from ltfj.gfs_features import FIELDS
from ltfj.model_gfs import GFS, fixed_model


class GfsModelTests(unittest.TestCase):
    def test_fixed_incremental_feature_set(self):
        self.assertEqual(len(GFS), 20)
        self.assertEqual(set(GFS), ({f"gfs_{field}_current" for field in FIELDS} |
                                    {f"gfs_{field}_change_3h" for field in FIELDS}))

    def test_model_configuration_is_frozen_without_early_stopping(self):
        model = fixed_model()
        self.assertFalse(model.early_stopping)
        self.assertEqual(model.max_leaf_nodes, 7)
        self.assertEqual(model.min_samples_leaf, 100)
        self.assertEqual(model.l2_regularization, 10)


if __name__ == "__main__":
    unittest.main()
