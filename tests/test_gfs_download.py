import tempfile
from pathlib import Path
import unittest
import numpy as np
from scipy.io import netcdf_file
from ltfj.archive_probe import VARIABLES
from ltfj.gfs_download import decode, UNITS


class GridTests(unittest.TestCase):
    def fixture(self, path, omit=None, wrong_time=False, fill=False):
        with netcdf_file(path, "w") as nc:
            for name, values, units in [
                ("latitude", [41], "degrees_north"), ("longitude", [29.25], "degrees_east"),
                ("time", [9 if wrong_time else 6], "Hour since 2021-01-15T00:00:00Z"),
                ("isobaric", [85000, 92500], "Pa"),
                ("isobaric2", [92500, 70000, 85000], "Pa")]:
                nc.createDimension(name, len(values))
                v = nc.createVariable(name, "d", (name,)); v[:] = values; v.units = units
            v = nc.createVariable("reftime", "d", ())
            v.data[...] = 0; v.units = "Hour since 2021-01-15T00:00:00Z"
            for i, name in enumerate(VARIABLES):
                if name == omit:
                    continue
                axis = "isobaric" if i % 2 == 0 else "isobaric2"
                v = nc.createVariable(name, "d", ("time", axis, "latitude", "longitude"))
                v.units = UNITS[name]
                values = [10, 20] if axis == "isobaric" else [30, 40, 50]
                v[:] = np.array(values).reshape(1, len(values), 1, 1)
                if fill:
                    v.missing_value = -9999.; v[:] = -9999.

    def test_each_variable_uses_own_pressure_axis(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"sample.nc"; self.fixture(path)
            result = decode(path, "2021011500", 6)
            self.assertEqual(result["Temperature_isobaric_925"], 20)
            self.assertEqual(result["Relative_humidity_isobaric_925"], 30)
            self.assertEqual(result["Relative_humidity_isobaric_850"], 50)

    def test_missing_variable_wrong_time_and_fill_are_rejected(self):
        for kwargs in [dict(omit=VARIABLES[1]), dict(wrong_time=True), dict(fill=True)]:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/"sample.nc"; self.fixture(path, **kwargs)
                with self.assertRaises((ValueError, KeyError)):
                    decode(path, "2021011500", 6)
