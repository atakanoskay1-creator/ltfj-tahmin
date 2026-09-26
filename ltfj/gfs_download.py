"""Resumable one-cell GFS grid acquisition with strict coordinate validation."""
import argparse
import csv
from datetime import timedelta
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import numpy as np
from scipy.io import netcdf_file

from .archive_probe import VARIABLES, gfs_url
from .pipeline import iso, timestamp, write_csv, write_json
from .sources import download

UNITS = dict(zip(VARIABLES, ["K", "%", "m/s", "m/s", "gpm"]))


def grid_url(cycle, lead):
    parts = urlsplit(gfs_url(cycle, lead))
    query = parse_qs(parts.query)
    for key in ["latitude", "longitude", "vertCoord"]:
        query.pop(key)
    query.update(north=[41.0], south=[41.0], east=[29.25], west=[29.25], accept=["netcdf"])
    return parts._replace(query=urlencode(query, doseq=True)).geturl()


def text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def time_value(variable):
    units = text(variable.units)
    prefix, base = units.split(" since ")
    if prefix.lower() not in {"hour", "hours"} or variable.data.size != 1:
        raise ValueError("Unexpected forecast time coordinate")
    return timestamp(base) + timedelta(hours=float(variable.data.reshape(-1)[0]))


def decode(path, cycle, lead):
    run = timestamp(f"{cycle[:4]}-{cycle[4:6]}-{cycle[6:8]}T{cycle[8:10]}:00Z")
    out = dict(cycle=iso(run), lead_hours=lead, valid_time=iso(run+timedelta(hours=lead)))
    with netcdf_file(path, mmap=False) as nc:
        if time_value(nc.variables["reftime"]) != run:
            raise ValueError("Wrong initialization time")
        for name, expected, units in [("latitude", 41.0, "degrees_north"),
                                       ("longitude", 29.25, "degrees_east")]:
            coord = nc.variables[name]
            if text(coord.units) != units or coord.data.size != 1 or not np.isclose(float(coord.data[0]), expected):
                raise ValueError("Wrong grid location or units")
        for name in VARIABLES:
            variable = nc.variables[name]  # Missing fields fail closed.
            if text(variable.units) != UNITS[name]:
                raise ValueError(f"Wrong units: {name}")
            dims = variable.dimensions
            pressure_dims = [d for d in dims if d.startswith("isobaric")]
            time_dims = [d for d in dims if d.startswith("time")]
            if len(pressure_dims) != 1 or len(time_dims) != 1:
                raise ValueError("Ambiguous coordinates")
            if time_value(nc.variables[time_dims[0]]) != run + timedelta(hours=lead):
                raise ValueError("Wrong forecast valid time")
            pressure = nc.variables[pressure_dims[0]]
            if text(pressure.units) != "Pa":
                raise ValueError("Pressure must be in Pa")
            for level in [925, 850]:
                indices = np.flatnonzero(pressure.data == level*100)
                if len(indices) != 1:
                    raise ValueError("Missing or duplicate pressure level")
                index = []
                for dim in dims:
                    if dim == pressure_dims[0]:
                        index.append(int(indices[0]))
                    elif nc.variables[dim].data.size == 1:
                        index.append(0)
                    else:
                        raise ValueError("Unexpected non-singleton dimension")
                value = float(variable.data[tuple(index)])
                if not np.isfinite(value) or any(value == float(getattr(variable, attr))
                        for attr in ["_FillValue", "missing_value"] if hasattr(variable, attr)):
                    raise ValueError("Missing forecast value")
                if name == "Relative_humidity_isobaric" and not 0 <= value <= 100:
                    raise ValueError("Humidity outside percent bounds")
                out[f"{name}_{level}"] = value
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--limit", type=int, default=48, help="Maximum files attempted; 0 audits cache only")
    parser.add_argument("--start", default="2020-12-31")
    parser.add_argument("--end", default="2026-09-21")
    parser.add_argument("--max-seconds", type=float, default=300,
                        help="Soft batch duration; an in-flight request may finish afterwards")
    parser.add_argument("--timeout", type=float, default=30, help="Per-request socket timeout")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("limit must be non-negative")
    if args.max_seconds <= 0 or args.timeout <= 0:
        parser.error("duration and timeout must be positive")
    if args.audit:
        plan = [(f"{year}{month:02d}1500", 6) for year in range(2021, 2027) for month in [1,4,7]]
    else:
        with Path("data/processed/research/gfs-acquisition-plan.csv").open() as handle:
            plan = [(timestamp(r["cycle"]).strftime("%Y%m%d%H"), int(r["lead_hours"]))
                    for r in csv.DictReader(handle) if args.start <= r["cycle"][:10] < args.end]
    root = Path("data/raw/gfs-grid")
    results, failures, completed, provenance = [], [], [], []
    attempts = 0
    started = time.monotonic()
    name = "gfs-grid-audit" if args.audit else "gfs-grid-progress"
    def checkpoint(final=False):
        write_json(Path(f"reports/{name}.json"), dict(scope="seasonal audit" if args.audit else "acquisition plan",
            start=args.start, end=args.end, planned=len(plan), validated=len(results),
            attempted_this_run=attempts, remaining=len(plan)-len(results),
            completed_this_run=completed, failures=failures, sources=provenance,
            scan_complete=final, elapsed_seconds=round(time.monotonic()-started, 2),
            note="Partial acquisition; scan_complete means cache scan finished, not full data acquired. Historical publication latency assumed."))
    for cycle, lead in plan:
        path = root/f"{cycle}_f{lead:03d}.nc"
        output = path.with_suffix(".validated.json")
        if output.exists():
            saved = json.loads(output.read_text())
            if saved["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError("Validated cache hash mismatch")
            results.append(saved["values"])
            provenance.append(json.loads(path.with_suffix(".nc.source.json").read_text()))
            continue
        if attempts >= args.limit or time.monotonic()-started >= args.max_seconds:
            continue
        attempts += 1
        try:
            download(grid_url(cycle, lead), path, timeout=args.timeout, attempts=2)
            values = decode(path, cycle, lead)
            write_json(output, dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), values=values))
            results.append(values); completed.append(path.name)
            provenance.append(json.loads(path.with_suffix(".nc.source.json").read_text()))
            print("Validated", path.name, flush=True)
        except Exception as exc:
            failures.append(dict(cycle=cycle, lead=lead, error=str(exc)))
        checkpoint()
    checkpoint(final=True)
    if results:
        write_csv(Path(f"data/processed/research/{name}.csv"), results)


if __name__ == "__main__":
    main()
