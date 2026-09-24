"""Outcome-independent seasonal GFS availability audit and causal cycle selection."""
import csv
import io
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .archive_probe import gfs_url, validate_sample
from .pipeline import write_json
from .sources import download, verified


def select_cycle(origin, cycles, delay_hours=6, max_age_hours=12):
    """Use a declared availability assumption; never equate initialization with receipt."""
    if delay_hours < 0 or max_age_hours < delay_hours:
        raise ValueError("Invalid availability assumptions")
    eligible = [c for c in cycles if c + timedelta(hours=delay_hours) <= origin
                and origin - c <= timedelta(hours=max_age_hours)]
    return max(eligible) if eligible else None


def forecast_bracket(origin, cycle, horizon_hours=3):
    """Required 3-hourly lead times around the target; no observations interpolated."""
    if cycle > origin or horizon_hours <= 0:
        raise ValueError("Future cycle or invalid horizon")
    lead = (origin + timedelta(hours=horizon_hours) - cycle).total_seconds()/3600
    low = int(lead//3)*3
    high = low if lead == low else low+3
    return low, high


def sample(cycle, level):
    url = gfs_url(cycle, pressure_pa=level*100)
    # Single-variable requests avoid the old-file combined-coordinate CSV bug.
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    query["var"] = ["Relative_humidity_isobaric"]
    url = parts._replace(query=urlencode(query, doseq=True)).geturl()
    path = Path(f"data/raw/gfs-coverage/{cycle}_f006_{level}_rh.csv")
    download(url, path)
    content, source = verified(path)
    rows = list(csv.DictReader(io.StringIO(content)))
    validate_sample(rows, cycle, 6, ["Relative_humidity_isobaric"])
    row = rows[0]
    humidity = float(row['Relative_humidity_isobaric[unit="%"]'])
    lat = float(row['latitude[unit="degrees_north"]'])
    lon = float(row['longitude[unit="degrees_east"]'])
    if not 0 <= humidity <= 100 or abs(lat-40.9) > .26 or abs(lon-29.3) > .26:
        raise ValueError("Unexpected units, humidity range or grid location")
    return dict(cycle=cycle, level_hpa=level, status="ok", humidity_percent=humidity,
                valid_time=row["time"], grid_latitude=lat, grid_longitude=lon, source=source)


def main():
    # Fixed before acquisition; no target labels consulted.
    plan = [(f"{year}{month:02d}1500", level) for year in range(2021, 2027)
            for month in [1, 4, 7] for level in [925, 850]]
    report = dict(plan=plan, purpose="Availability only, not model performance",
        selection="15 January/April/July 00 UTC, 2021–2026, +6h, 925/850 hPa",
        limitations="Sparse samples cannot establish complete coverage. Only RH tested here. Publication latency unknown.", samples=[])
    for cycle, level in plan:
        try:
            result = sample(cycle, level)
        except Exception as exc:
            result = dict(cycle=cycle, level_hpa=level, status="failed", error=str(exc))
        report["samples"].append(result)
        report["successful"] = sum(r["status"] == "ok" for r in report["samples"])
        report["attempted"] = len(report["samples"])
        write_json(Path("reports/gfs-coverage.json"), report)
        print(cycle, level, result["status"], flush=True)


if __name__ == "__main__":
    main()
