"""Evaluate the frozen local and GFS research models on a prepared timestamp."""
import argparse
import csv
import json
from pathlib import Path

import joblib

from .model import adjusted, matrix
from .pipeline import iso, timestamp


def find_row(path, at):
    with path.open(encoding="utf-8") as handle:
        return next((row for row in csv.DictReader(handle) if timestamp(row["time"]) == at), None)


def state(row):
    if row["below_500"] == "True":
        return "already_below_threshold"
    if row["below_500"] != "False" or not row["observation_age_minutes"] or float(row["observation_age_minutes"]) > 35:
        return "insufficient_current_observation"
    return "research_estimate"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", required=True, type=timestamp)
    parser.add_argument("--folder", type=Path, default=Path("data/processed/research"))
    parser.add_argument("--model", type=Path, default=Path("models/ceiling-risk-gfs.joblib"))
    args = parser.parse_args()
    row = find_row(args.folder / "features.csv", args.at)
    gfs = find_row(args.folder / "gfs-features.csv", args.at)
    if row is None:
        raise ValueError("Requested time is absent from prepared METAR features")
    condition = state(row)
    output = {"time": iso(args.at), "status": condition, "local_probability": None,
              "gfs_probability": None, "local_alarm": None, "gfs_alarm": None}
    if condition == "research_estimate":
        artifact = joblib.load(args.model)
        combined = dict(row, **(gfs or {}))
        for name, prefix in [("matched_local", "local"), ("matched_local_gfs", "gfs")]:
            if name == "matched_local_gfs" and (not gfs or gfs.get("gfs_status") != "available_under_assumption"):
                continue
            meta = artifact["metadata"][name]
            raw = artifact["models"][name].predict_proba(matrix([combined], meta["columns"]))[0, 1]
            probability = float(adjusted([raw], meta["offset"])[0])
            output[prefix + "_probability"] = probability
            output[prefix + "_alarm"] = probability >= meta["threshold"]
    output["note"] = "Prepared historical research estimate; live data acquisition is a separate step."
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
