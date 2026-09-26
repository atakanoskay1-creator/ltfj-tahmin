"""Match validated GFS fields to METAR origins under an explicit latency assumption."""
import csv
import json
from datetime import timedelta
from pathlib import Path
import hashlib

from .archive_probe import VARIABLES
from .gfs_coverage import forecast_bracket
from .pipeline import iso, timestamp, write_csv, write_json

FIELDS = [f"{v}_{level}" for v in VARIABLES for level in [925,850]]


def at_origin(origin, records, delay_hours=6):
    if delay_hours < 0:
        raise ValueError("Negative latency")
    cutoff = origin-timedelta(hours=delay_hours)
    cycle = cutoff.replace(hour=cutoff.hour//6*6, minute=0, second=0, microsecond=0)
    key = iso(cycle)
    values = []
    for horizon in [0, 3]:
        lo, hi = forecast_bracket(origin, cycle, horizon)
        a, b = records.get((key, lo)), records.get((key, hi))
        if a is None or b is None:
            return dict(gfs_status="missing_required_forecast", gfs_cycle=key)
        target_lead = (origin-cycle).total_seconds()/3600+horizon
        weight = 0 if lo == hi else (target_lead-lo)/(hi-lo)
        values.append({f: a[f]*(1-weight)+b[f]*weight for f in FIELDS})
    return dict(gfs_status="available_under_assumption", gfs_cycle=key,
        **{f"gfs_{f}_current": values[0][f] for f in FIELDS},
        **{f"gfs_{f}_change_3h": values[1][f]-values[0][f] for f in FIELDS})


def main():
    records = {}
    for path in Path("data/raw/gfs-grid").glob("*.validated.json"):
        saved = json.loads(path.read_text())
        raw = Path(str(path).replace(".validated.json", ".nc"))
        if hashlib.sha256(raw.read_bytes()).hexdigest() != saved["sha256"]:
            raise ValueError("Validated source changed")
        r = saved["values"]; records[(r["cycle"], r["lead_hours"])] = r
    folder = Path("data/processed/research")
    with (folder/"features.csv").open(encoding="utf-8") as handle:
        times = [r["time"] for r in csv.DictReader(handle)]
    # Sensitivity scenarios report coverage only; no refitting or test-set threshold choice.
    result, summaries = [], {}
    for delay in [6,9,12]:
        rows = [dict(time=t, **at_origin(timestamp(t), records, delay)) for t in times]
        summaries[str(delay)] = dict(origins=len(rows), available=sum(
            r["gfs_status"] == "available_under_assumption" for r in rows))
        if delay == 6:
            result = rows
    columns = ["time", "gfs_status", "gfs_cycle"] + [
        f"gfs_{f}_{suffix}" for suffix in ["current", "change_3h"] for f in FIELDS]
    write_csv(folder/"gfs-features.csv", [{k: row.get(k) for k in columns} for row in result])
    write_json(Path("reports/gfs-feature-coverage.json"), dict(validated_forecast_files=len(records),
        coverage_by_assumed_delay_hours=summaries,
        note="Partial acquisition. Missing forecasts stay missing; no performance estimate. Linear interpolation is of forecasts from one cycle only."))


if __name__ == "__main__":
    main()
