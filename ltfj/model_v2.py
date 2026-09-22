"""Fixed nonlinear comparison with rolling-origin selection and reused replay."""
import csv
import hashlib
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from .model import (LOCAL, NEIGHBOR, adjusted, alarm_threshold, block_intervals,
                    calibrate_offset, event_scores, load_dataset, matrix, scores, split_indices)
from .pipeline import timestamp, write_json

REDUCED = ["log_ceiling", "no_ceiling", "spread_c", "log_visibility", "wind_u",
           "wind_v", "qnh_hpa", "hour_sin", "hour_cos", "year_sin", "year_cos",
           "spread_change_1h", "pressure_change_3h", "recent_low_fraction"]


def candidate(name):
    columns = LOCAL + NEIGHBOR if name.endswith("neighbors") else REDUCED if name.endswith("reduced") else LOCAL
    if name.startswith("boost"):
        model = HistGradientBoostingClassifier(max_iter=150, learning_rate=.05,
            max_leaf_nodes=7, min_samples_leaf=100, l2_regularization=10,
            early_stopping=False, random_state=20260922)
    else:
        steps = [SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)]
        if name.startswith("spline"):
            steps.append(SplineTransformer(n_knots=4, degree=2, knots="quantile", include_bias=False))
        steps.extend([StandardScaler(), LogisticRegression(C=.01, max_iter=5000, tol=1e-7)])
        model = make_pipeline(*steps)
    return model, columns


def main():
    warnings.filterwarnings("error", category=ConvergenceWarning)
    protocol_path = Path("research-protocol-v2.json")
    protocol = json.loads(protocol_path.read_text())
    folder = Path("data/processed/research")
    rows, y = load_dataset(folder)
    embargo = protocol["boundary_embargo_hours"]
    candidates = []
    for name in protocol["candidates"]:
        fold_scores, yy, pp = [], [], []
        for start, boundary, end in protocol["selection_folds"]:
            train = split_indices(rows, start, boundary, embargo)
            valid = split_indices(rows, boundary, end, embargo)
            model, columns = candidate(name)
            x = matrix(rows, columns)
            model.fit(x[train], y[train])
            p = model.predict_proba(x[valid])[:, 1]
            fold_scores.append(dict(year=boundary[:4], **scores(y[valid], p)))
            yy.extend(y[valid]); pp.extend(p)
        item = dict(name=name, folds=fold_scores, pooled=scores(np.array(yy), np.array(pp)))
        candidates.append(item)
        print(name, item["pooled"], flush=True)
    winner = min(candidates, key=lambda r: r["pooled"]["brier"])
    model, columns = candidate(winner["name"])
    x = matrix(rows, columns)
    train = split_indices(rows, *protocol["final_train"], embargo)
    calibration = split_indices(rows, *protocol["calibration"], embargo)
    model.fit(x[train], y[train])
    raw = model.predict_proba(x)[:, 1]
    offset = calibrate_offset(y[calibration], raw[calibration])
    p = adjusted(raw, offset)
    threshold = alarm_threshold(y[calibration], p[calibration], protocol["alarm_recall_goal"])
    frozen = dict(protocol=protocol, selected=winner["name"], columns=columns,
        offset=offset, threshold=threshold, candidates=candidates,
        hashes={str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [protocol_path, folder/"features.csv", folder/"labels.csv"]})
    write_json(Path("models/v2-frozen-selection.json"), frozen)
    joblib.dump(dict(pipeline=model, metadata=frozen), "models/ceiling-risk-v2.joblib")
    # Only the selected model is replayed; replay never determines a candidate.
    v1 = joblib.load("models/ceiling-risk.joblib")
    ref = adjusted(v1["pipeline"].predict_proba(matrix(rows, v1["columns"]))[:, 1], v1["offset"])
    results = {}
    with (folder/"observations.csv").open(encoding="utf-8") as handle:
        observations = [dict(time=timestamp(r["time"]),
            below_500={"True": True, "False": False}.get(r["below_500"]),
            ceiling_ft=float(r["ceiling_ft"]) if r["ceiling_ft"] else None)
            for r in csv.DictReader(handle)]
    for start, end in [protocol["calibration"], *protocol["replay"]]:
        ix = split_indices(rows, start, end, embargo if start[:4] == "2024" else 0)
        results[start[:4]] = dict(v2=scores(y[ix], p[ix], threshold),
            v2_raw=scores(y[ix], raw[ix]), v1=scores(y[ix], ref[ix], v1["threshold"]),
            uncertainty_vs_v1=block_intervals(y[ix], p[ix], ref[ix],
                [timestamp(rows[i]["time"]) for i in ix], threshold))
        results[start[:4]]["events"] = event_scores(observations,
            [timestamp(rows[i]["time"]) for i in ix], p[ix], threshold, start, end)
    development_errors = {}
    for name, predicate in {
        "no_numeric_ceiling": lambda r: not r["ceiling_ft"],
        "ceiling_500_999": lambda r: bool(r["ceiling_ft"]) and float(r["ceiling_ft"]) < 1000,
        "ceiling_at_least_1000": lambda r: bool(r["ceiling_ft"]) and float(r["ceiling_ft"]) >= 1000,
    }.items():
        ix = np.array([i for i in calibration if predicate(rows[i])], dtype=int)
        if len(ix):
            development_errors[name] = scores(y[ix], p[ix], threshold)
    write_json(Path("reports/model-v2-results.json"), dict(frozen=frozen, results=results,
        development_errors=development_errors))
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
