"""Fail closed before training on a partially downloaded forecast archive."""
import csv
import json
import math
from pathlib import Path
from datetime import timedelta

from .gfs_features import FIELDS
from .pipeline import timestamp, write_json

FEATURES = [f"gfs_{f}_{suffix}" for suffix in ["current", "change_3h"] for f in FIELDS]


def audit(labels, features, protocol):
    if len(labels) != len(features) or any(a["time"] != b["time"] for a,b in zip(labels, features)):
        raise ValueError("GFS/label alignment mismatch")
    if len({r["time"] for r in labels}) != len(labels):
        raise ValueError("Duplicate origin")
    years = {str(year): dict(eligible=0, available=0, positives=0, available_positives=0)
             for year in protocol["coverage_years"]}
    delay = timedelta(hours=protocol["assumed_publication_delay_hours"])
    invalid = []
    for label, feature in zip(labels, features):
        if label["below_500_within_3h"] not in {"0", "1"}:
            continue
        year = label["time"][:4]
        if year not in years:
            continue
        count = years[year]; positive = int(label["below_500_within_3h"])
        count["eligible"] += 1; count["positives"] += positive
        available = feature["gfs_status"] == "available_under_assumption"
        if available:
            try:
                cycle = timestamp(feature["gfs_cycle"])
                age = timestamp(label["time"]) - cycle
                valid = delay <= age < delay+timedelta(hours=6)
                valid = valid and all(math.isfinite(float(feature[name])) for name in FEATURES)
            except (ValueError, KeyError, TypeError):
                valid = False
            if not valid:
                invalid.append(label["time"])
                available = False
        count["available"] += int(available)
        count["available_positives"] += positive*int(available)
    for count in years.values():
        count["coverage"] = count["available"]/count["eligible"] if count["eligible"] else 0.
        count["positive_coverage"] = count["available_positives"]/count["positives"] if count["positives"] else 0.
        count["passes"] = (count["coverage"] >= protocol["minimum_yearly_eligible_origin_coverage"]
            and count["positive_coverage"] >= protocol["minimum_yearly_positive_origin_coverage"])
    return dict(ready=not invalid and all(c["passes"] for c in years.values()),
        years=years, invalid_available_origins=invalid,
        note="Coverage prerequisite only, not proof of forecast skill or historical availability.")


def main():
    folder = Path("data/processed/research")
    protocol = json.loads(Path("gfs-experiment-protocol.json").read_text())
    with (folder/"labels.csv").open(encoding="utf-8") as handle:
        labels = list(csv.DictReader(handle))
    with (folder/"gfs-features.csv").open(encoding="utf-8") as handle:
        features = list(csv.DictReader(handle))
    report = audit(labels, features, protocol)
    write_json(Path("reports/gfs-training-readiness.json"), report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
