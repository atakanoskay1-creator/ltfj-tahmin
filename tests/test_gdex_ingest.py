import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scipy.io import netcdf_file

from ltfj import gdex_ingest
from ltfj.gdex_ingest import NAMES, UNITS, decode, expected_cycles, ingest
from ltfj.gfs_features import add


def sample(cycle="2020123118", lead=6, levels=(925, 850), units=None, rh=57.9, lat=41.0):
    """Build a NetCDF3 file shaped like a GDEX single-cell subset."""
    handle = io.BytesIO()
    nc = netcdf_file(handle, "w")
    for name, size in [("time", 1), ("level0", 2), ("lat", 1), ("lon", 1), ("tstrlen", 10)]:
        nc.createDimension(name, size)
    time = nc.createVariable("time", "f", ("time",))
    time.units = "hours since 2020-12-31 00:00:00.0 +0:00"
    valid = gdex_ingest.run_time(cycle) + gdex_ingest.timedelta(hours=lead)
    time[:] = (valid - gdex_ingest.run_time("2020123100")).total_seconds()/3600
    for name, value in [("valid_date_time", valid.strftime("%Y%m%d%H")), ("ref_date_time", cycle)]:
        nc.createVariable(name, "c", ("time", "tstrlen"))[:] = np.array([list(value)], dtype="S1")
    hour = nc.createVariable("forecast_hour", "i", ("time",)); hour[:] = lead; hour.units = "hours"
    level = nc.createVariable("level0", "f", ("level0",)); level[:] = levels; level.units = "mbar"
    for name, value, unit in [("lat", lat, "degree_north"), ("lon", 29.25, "degree_east")]:
        coord = nc.createVariable(name, "f", (name,)); coord[:] = value; coord.units = unit
    for name in NAMES:
        variable = nc.createVariable(name, "f", ("time", "level0", "lat", "lon"))
        variable[:] = rh if name == "R_H_L100" else 280.
        variable.units = (units or UNITS)[name]
        variable.product_description = f"{lead}-hour Forecast"
        variable._FillValue = np.float32(3.4e38)
    nc.flush()
    payload = handle.getvalue()
    nc.close()
    return payload


class DecodeTests(unittest.TestCase):
    def test_valid_subset_maps_to_thredds_field_names(self):
        record = decode(sample(), "2020123118", 6)
        self.assertEqual(record["cycle"], "2020-12-31T18:00:00Z")
        self.assertEqual(record["valid_time"], "2021-01-01T00:00:00Z")
        self.assertAlmostEqual(record["Relative_humidity_isobaric_850"], 57.9, places=4)
        self.assertEqual(len(record), 3 + 10)

    def test_wrong_metadata_fails_closed(self):
        bad = [sample(lead=9), sample(levels=(850, 925)), sample(rh=101.), sample(lat=40.75),
               sample(units=UNITS | {"U_GRD_L100": "knots"})]
        for payload in bad:
            with self.assertRaises(ValueError):
                decode(payload, "2020123118", 6)

    def test_expected_cycles_are_six_hourly_and_inclusive(self):
        cycles = expected_cycles(dict(date="202601010000/to/202601011200"))
        self.assertEqual(cycles, ["2026010100", "2026010106", "2026010112"])


class IngestTests(unittest.TestCase):
    def archive(self, folder, members):
        folder.mkdir(parents=True)
        with tarfile.open(folder/"subset.tar", "w") as tar:
            for name, payload in members:
                info = tarfile.TarInfo(name); info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))

    def test_coverage_reports_missing_leads_and_cycles(self):
        control = dict(date="202012311200/to/202012311800")
        with tempfile.TemporaryDirectory() as tmp, patch.object(gdex_ingest, "ROOT", Path(tmp)):
            self.archive(Path(tmp)/"tail", [(f"gfs.0p25.2020123118.f{lead:03d}.grib2.nc",
                sample(lead=lead)) for lead in [6, 9, 12]])
            records, sources, coverage = ingest("tail", control)
        self.assertEqual(len(records), 3)
        self.assertEqual(len(sources[0]["sha256"]), 64)
        self.assertEqual(coverage["missing_cycles"], ["2020123112"])
        self.assertEqual(coverage["missing_leads_by_cycle"], {"2020123118": [15]})

    def test_unexpected_or_out_of_request_members_are_rejected(self):
        control = dict(date="202012311800/to/202012311800")
        for name in ["../gfs.0p25.2020123118.f006.grib2.nc", "gfs.0p25.2021010100.f006.grib2.nc"]:
            with tempfile.TemporaryDirectory() as tmp, patch.object(gdex_ingest, "ROOT", Path(tmp)):
                self.archive(Path(tmp)/"tail", [(name, sample())])
                with self.assertRaises(ValueError):
                    ingest("tail", control)


class MergeTests(unittest.TestCase):
    def test_transports_must_agree_on_shared_forecasts(self):
        record = decode(sample(), "2020123118", 6)
        records = {}
        add(records, record); add(records, dict(record))
        with self.assertRaises(ValueError):
            add(records, record | {"Temperature_isobaric_925": 281.})


if __name__ == "__main__":
    unittest.main()
