from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ltfj.sources import download


class RetryTests(unittest.TestCase):
    def test_failed_download_is_bounded_and_not_cached(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"sample.nc"
            with patch("ltfj.sources.urlopen", side_effect=TimeoutError("slow")) as opener, \
                 patch("ltfj.sources.time.sleep"):
                with self.assertRaises(TimeoutError):
                    download("https://example.org/sample", path, timeout=2, attempts=2)
                self.assertEqual(opener.call_count, 2)
                self.assertEqual(opener.call_args.kwargs["timeout"], 2)
            self.assertFalse(path.exists())
            self.assertFalse(path.with_suffix(".nc.source.json").exists())

    def test_invalid_limits_fail_before_network(self):
        with patch("ltfj.sources.urlopen") as opener:
            with self.assertRaises(ValueError):
                download("https://example.org/sample", Path("unused"), attempts=0)
            opener.assert_not_called()
