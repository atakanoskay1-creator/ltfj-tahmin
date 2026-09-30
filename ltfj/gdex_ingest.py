"""Safely unpack and validate GDEX batch NetCDF output."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import tarfile
from pathlib import Path

import numpy as np
from scipy.io import netcdf_file

from .pipeline import iso, write_json

FILE_RE = re.compile(r"gfs\.0p25\.(\d{10})\.f(006|009|012|015)\.grib2\.nc$")
VARIABLES = {
    "TMP_L100": ("Temperature_isobaric", "K"),
    "R_H_L100": ("Relative_humidity_isobaric", "%"),
    "U_GRD_L100": ("u-component_of_wind_isobaric", "m s-1"),
    "V_GRD_L100": ("v-component_of_wind_isobaric", "m s-1"),
    "HGT_L100": ("Geopotential_height_isobaric", "gpm"),
}


def text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def chars(variable):
    return b"".join(np.asarray(variable.data).reshape(-1).tolist()).decode("ascii")


def safe_unpack(path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(path) as archive:
        members = [m for m in archive.getmembers() if m.isfile()]
        for member in members:
            if Path(member.name).name != member.name or not FILE_RE.fullmatch(member.name):
                raise ValueError(f"Unexpected archive member: {member.name}")
            if not (root / member.name).resolve().is_relative_to(root):
                raise ValueError("Unsafe archive path")
        archive.extractall(destination, members=members, filter="data")
    return [destination / member.name for member in members]


def validate(path):
    match = FILE_RE.fullmatch(path.name)
    if not match:
        raise ValueError("Unexpected GFS filename")
    cycle = datetime.strptime(match.group(1), "%Y%m%d%H").replace(tzinfo=timezone.utc)
    lead = int(match.group(2))
    with netcdf_file(path, mmap=False) as nc:
        for coord, expected, units in [("lat", 41.0, "degree_north"), ("lon", 29.25, "degree_east")]:
            var = nc.variables[coord]
            if text(var.units) != units or var.data.size != 1 or not np.isclose(float(var.data[0]), expected):
                raise ValueError(f"Wrong {coord} coordinate")
        levels = nc.variables["level0"]
        if text(levels.units) != "mbar" or set(map(float, levels.data)) != {850.0, 925.0}:
            raise ValueError("Wrong pressure levels")
        if int(nc.variables["forecast_hour"].data[0]) != lead:
            raise ValueError("Wrong forecast lead")
        if chars(nc.variables["ref_date_time"]) != cycle.strftime("%Y%m%d%H"):
            raise ValueError("Wrong initialization time")
        valid = cycle + timedelta(hours=lead)
        if chars(nc.variables["valid_date_time"]) != valid.strftime("%Y%m%d%H"):
            raise ValueError("Wrong valid time")
        result = {"cycle": iso(cycle), "lead_hours": lead, "valid_time": iso(valid)}
        for source, (target, units) in VARIABLES.items():
            var = nc.variables[source]
            if text(var.units) != units or var.dimensions != ("time", "level0", "lat", "lon"):
                raise ValueError(f"Wrong units or dimensions: {source}")
            for level in [925, 850]:
                index = int(np.flatnonzero(levels.data == level)[0])
                value = float(var.data[0, index, 0, 0])
                if not np.isfinite(value):
                    raise ValueError(f"Missing value: {source}")
                if source == "R_H_L100" and not 0 <= value <= 100:
                    raise ValueError("Humidity outside bounds")
                result[f"{target}_{level}"] = value
    return result


def ingest(root=Path("data/raw/gdex-batch")):
    files = set(root.glob("**/*.nc"))
    for archive in root.glob("**/*.tar"):
        files.update(safe_unpack(archive, archive.parent))
    records = []
    for path in sorted(files):
        values = validate(path)
        sidecar = path.with_suffix(path.suffix + ".validated.json")
        write_json(sidecar, {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "values": values})
        records.append(values)
    report = {"validated_files": len(records), "cycles": len({r["cycle"] for r in records}),
              "first_cycle": records[0]["cycle"] if records else None,
              "last_cycle": records[-1]["cycle"] if records else None}
    write_json(Path("reports/gdex-ingest.json"), report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(ingest(), indent=2))


if __name__ == "__main__":
    main()
