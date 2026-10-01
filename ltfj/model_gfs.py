"""Fixed incremental GFS experiment with chronological development and replay."""
import csv
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from .gfs_features import FIELDS
from .model import (LOCAL, adjusted, alarm_threshold, block_intervals, calibrate_offset,
                    event_scores, load_dataset, matrix, scores, split_indices)
from .pipeline import timestamp, write_json

GFS = ([f"gfs_{field}_current" for field in FIELDS] +
       [f"gfs_{field}_change_3h" for field in FIELDS])


def fixed_model():
    return HistGradientBoostingClassifier(max_iter=150, learning_rate=.05,
        max_leaf_nodes=7, min_samples_leaf=100, l2_regularization=10,
        early_stopping=False, random_state=20260922)


def matched_dataset(folder):
    rows, y = load_dataset(folder)
    with (folder / "gfs-features.csv").open(encoding="utf-8") as handle:
        gfs = {row["time"]: row for row in csv.DictReader(handle)}
    matched_rows, matched_y = [], []
    for row, target in zip(rows, y):
        extra = gfs.get(row["time"])
        if extra and extra["gfs_status"] == "available_under_assumption" and all(extra.get(k) not in {None, ""} for k in GFS):
            matched_rows.append(dict(row, **extra))
            matched_y.append(target)
    return rows, y, matched_rows, np.asarray(matched_y, dtype=int)


def main():
    folder = Path("data/processed/research")
    protocol_path = Path("gfs-experiment-protocol.json")
    protocol = json.loads(protocol_path.read_text())
    readiness = json.loads(Path("reports/gfs-training-readiness.json").read_text())
    if not readiness["ready"]:
        raise RuntimeError("GFS coverage gate has not passed")
    all_rows, all_y, rows, y = matched_dataset(folder)
    embargo = 24
    train = split_indices(rows, *protocol["development_train"], embargo)
    calibration = split_indices(rows, *protocol["calibration"], embargo)
    models, probabilities, metadata = {}, {}, {}
    for name, columns in {"matched_local": LOCAL, "matched_local_gfs": LOCAL + GFS}.items():
        model = fixed_model()
        x = matrix(rows, columns)
        model.fit(x[train], y[train])
        raw = model.predict_proba(x)[:, 1]
        offset = calibrate_offset(y[calibration], raw[calibration])
        calibrated = adjusted(raw, offset)
        threshold = alarm_threshold(y[calibration], calibrated[calibration], .70)
        models[name] = model
        probabilities[name] = calibrated
        metadata[name] = {"columns": columns, "offset": offset, "threshold": threshold}
    artifact = {"models": models, "metadata": metadata, "protocol": protocol}
    joblib.dump(artifact, "models/ceiling-risk-gfs.joblib")

    frozen_v2 = joblib.load("models/ceiling-risk-v2.joblib")
    all_v2 = adjusted(frozen_v2["pipeline"].predict_proba(
        matrix(all_rows, frozen_v2["metadata"]["columns"]))[:, 1], frozen_v2["metadata"]["offset"])
    with (folder / "observations.csv").open(encoding="utf-8") as handle:
        observations = [dict(time=timestamp(r["time"]),
            below_500={"True": True, "False": False}.get(r["below_500"]),
            ceiling_ft=float(r["ceiling_ft"]) if r["ceiling_ft"] else None)
            for r in csv.DictReader(handle)]

    periods = [("calibration_2024", protocol["calibration"])] + [
        (f"replay_{start[:4]}", [start, end]) for start, end in protocol["reused_replay"]]
    results = {}
    for label, (start, end) in periods:
        matched_ix = split_indices(rows, start, end, embargo if label == "calibration_2024" else 0)
        all_ix = split_indices(all_rows, start, end, embargo if label == "calibration_2024" else 0)
        times = [timestamp(rows[i]["time"]) for i in matched_ix]
        local = probabilities["matched_local"][matched_ix]
        gfs = probabilities["matched_local_gfs"][matched_ix]
        local_threshold = metadata["matched_local"]["threshold"]
        gfs_threshold = metadata["matched_local_gfs"]["threshold"]
        results[label] = {
            "matched_local": scores(y[matched_ix], local, local_threshold),
            "matched_local_gfs": scores(y[matched_ix], gfs, gfs_threshold),
            "all_origin_frozen_v2": scores(all_y[all_ix], all_v2[all_ix], frozen_v2["metadata"]["threshold"]),
            "paired_uncertainty_gfs_vs_local": block_intervals(y[matched_ix], gfs, local, times, gfs_threshold),
            "events_local": event_scores(observations, times, local, local_threshold, start, end),
            "events_gfs": event_scores(observations, times, gfs, gfs_threshold, start, end),
        }
        print(label, json.dumps(results[label]), flush=True)
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in
              [protocol_path, folder/"features.csv", folder/"labels.csv", folder/"gfs-features.csv"]}
    write_json(Path("reports/model-gfs-results.json"), {
        "protocol": protocol, "coverage_gate": readiness, "matched_rows": len(rows),
        "all_eligible_rows": len(all_rows), "frozen": metadata, "input_hashes": hashes,
        "results": results,
        "interpretation_limit": "2025 and 2026 are reused retrospective periods; historical GFS publication delay is assumed."})


if __name__ == "__main__":
    main()
