"""Validate NCAR GDEX server-side GFS subset archives and register their point values."""
from collections import Counter
from datetime import timedelta
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

import numpy as np
from scipy.io import netcdf_file

from .archive_probe import VARIABLES
from .gdex_batch import ROOT, controls
from .pipeline import iso, timestamp, write_json

# GDEX subset variable -> THREDDS name used by the existing feature code.
NAMES = dict(zip(["TMP_L100", "R_H_L100", "U_GRD_L100", "V_GRD_L100", "HGT_L100"], VARIABLES))
UNITS = dict(TMP_L100="K", R_H_L100="%", U_GRD_L100="m s-1", V_GRD_L100="m s-1", HGT_L100="gpm")
LEADS = [6, 9, 12, 15]
MEMBER = re.compile(r"gfs\.0p25\.(\d{10})\.f(\d{3})\.grib2\.nc")


def text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def chars(variable):
    return b"".join(variable.data.reshape(-1)).decode()


def run_time(cycle):
    return timestamp(f"{cycle[:4]}-{cycle[4:6]}-{cycle[6:8]}T{cycle[8:10]}:00Z")


def decode(payload, cycle, lead):
    """Return one record in the THREDDS decoder's layout; any surprise fails closed."""
    run = run_time(cycle)
    valid = run + timedelta(hours=lead)
    out = dict(cycle=iso(run), lead_hours=lead, valid_time=iso(valid))
    with netcdf_file(io.BytesIO(payload), mmap=False) as nc:
        v = nc.variables
        if set(v) != {"time", "valid_date_time", "ref_date_time", "forecast_hour",
                      "level0", "lat", "lon", *NAMES}:
            raise ValueError("Unexpected variable set")
        if chars(v["ref_date_time"]) != cycle or chars(v["valid_date_time"]) != valid.strftime("%Y%m%d%H"):
            raise ValueError("Wrong reference or valid time")
        if v["forecast_hour"].data.size != 1 or int(v["forecast_hour"].data[0]) != lead:
            raise ValueError("Wrong forecast hour")
        prefix, base = text(v["time"].units).split(" since ")
        if prefix != "hours" or v["time"].data.size != 1 or \
                timestamp(base.split(".")[0].replace(" ", "T") + "Z") + timedelta(hours=float(v["time"].data[0])) != valid:
            raise ValueError("Time coordinate disagrees with valid time")
        for name, expected, units in [("lat", 41.0, "degree_north"), ("lon", 29.25, "degree_east")]:
            coord = v[name]
            if text(coord.units) != units or coord.data.size != 1 or not np.isclose(float(coord.data[0]), expected):
                raise ValueError("Wrong grid location or units")
        levels = v["level0"]
        if text(levels.units) != "mbar" or list(levels.data) != [925, 850]:
            raise ValueError("Unexpected pressure levels")
        for name, target in NAMES.items():
            variable = v[name]
            if variable.dimensions != ("time", "level0", "lat", "lon") or variable.data.shape != (1, 2, 1, 1):
                raise ValueError(f"Unexpected shape: {name}")
            if text(variable.units) != UNITS[name]:
                raise ValueError(f"Wrong units: {name}")
            if text(variable.product_description) != f"{lead}-hour Forecast":
                raise ValueError(f"Wrong product: {name}")
            fill = float(variable._FillValue)
            for index, level in enumerate([925, 850]):
                value = float(variable.data[0, index, 0, 0])
                if not np.isfinite(value) or value == fill:
                    raise ValueError("Missing forecast value")
                if name == "R_H_L100" and not 0 <= value <= 100:
                    raise ValueError("Humidity outside percent bounds")
                out[f"{target}_{level}"] = value
    return out


def expected_cycles(control):
    start, end = [run_time(value[:10]) for value in control["date"].split("/to/")]
    cycles = []
    while start <= end:
        cycles.append(start.strftime("%Y%m%d%H")); start += timedelta(hours=6)
    return cycles


def ingest(name, control):
    """Read every archive in ROOT/name without extracting it; return records and coverage."""
    archives = sorted((ROOT/name).glob("*.tar"))
    if not archives:
        return None
    expected = set(expected_cycles(control))
    records, sources, seen = [], [], set()
    for archive in archives:
        payload = archive.read_bytes()
        sources.append(dict(file=archive.name, sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload)))
        with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
            for member in tar.getmembers():
                match = MEMBER.fullmatch(member.name)
                if not member.isfile() or not match:
                    raise ValueError(f"Unexpected archive member: {member.name}")
                cycle, lead = match.group(1), int(match.group(2))
                if cycle not in expected or lead not in LEADS or (cycle, lead) in seen:
                    raise ValueError(f"Outside request or duplicate: {member.name}")
                seen.add((cycle, lead))
                records.append(decode(tar.extractfile(member).read(), cycle, lead))
    leads = Counter(cycle for cycle, _ in seen)
    missing = sorted(expected - set(leads))
    partial = {c: sorted(set(LEADS) - {l for cc, l in seen if cc == c}) for c in sorted(leads) if leads[c] != len(LEADS)}
    coverage = dict(expected_cycles=len(expected), complete_cycles=sum(n == len(LEADS) for n in leads.values()),
        files=len(records), expected_files=len(expected)*len(LEADS),
        missing_cycles=missing, missing_leads_by_cycle=partial)
    return records, sources, coverage


def main():
    report = {}
    for name, control in controls().items():
        result = ingest(name, control)
        if result is None:
            report[name] = dict(status="not_downloaded")
            continue
        records, sources, coverage = result
        # Source hashes are stored so feature building can detect a changed archive.
        write_json(ROOT/name/"validated.json", dict(sources=sources, records=records))
        report[name] = dict(status="validated", sources=sources, **coverage)
        print(f"{name}: {len(records)} files validated, {len(coverage['missing_cycles'])} cycles missing", flush=True)
    write_json(Path("reports/gdex-ingest.json"), dict(requests=report,
        checks=["member names match request cycles and leads", "reference/valid time and forecast hour",
                "41N 29.25E single cell", "925/850 mbar levels", "five fields with expected units and product",
                "no fill values, humidity within 0-100 %"],
        note="Missing cycles are left missing. Archive time is not historical publication time."))


if __name__ == "__main__":
    main()
