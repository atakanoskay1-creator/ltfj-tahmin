import os
import unittest
from unittest.mock import patch
from ltfj.gdex_batch import PARAMETERS, PRODUCTS, control, controls, token


class BatchTests(unittest.TestCase):
    def test_controls_cover_needed_initializations_without_overlap(self):
        plan = controls()
        self.assertEqual(len(plan), 7)
        self.assertEqual(plan["2020_tail"]["date"], "202012311800/to/202012311800")
        self.assertEqual(plan["2026"]["date"], "202601010000/to/202609201200")
        for item in plan.values():
            self.assertEqual(item["datetype"], "init")
            self.assertEqual(item["param"], PARAMETERS)
            self.assertEqual(item["product"], PRODUCTS)
            self.assertEqual(item["level"], "ISBL:925/850")

    def test_bad_dates_and_missing_secret_fail_closed(self):
        with self.assertRaises(ValueError):
            control("202101020000", "202101010000")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                token()

    def test_token_is_read_from_environment_only(self):
        with patch.dict(os.environ, {"GDEX_TOKEN": " secret "}, clear=True):
            self.assertEqual(token(), "secret")
