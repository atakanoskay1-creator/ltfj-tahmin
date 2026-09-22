"""Descriptive development-period error audit; never tunes a model."""
import csv
from collections import Counter
from pathlib import Path

import joblib
import numpy as np

from .model import adjusted, load_dataset, matrix, scores, split_indices
from .pipeline import write_csv, write_json


def regimes(row):
    """Overlapping, observation-only strata; empty numeric fields stay unknown."""
    result = []
    for field, label in [("fog_mist", "fog_or_mist"), ("rain", "rain_or_drizzle")]:
        if row[field] == "1":
            result.append(label)
    if row["fog_mist"] == "0" and row["rain"] == "0":
        result.append("no_reported_fog_mist_rain")
    spread = row["spread_c"]
    result.append("spread_missing" if spread == "" else "spread_le_2c" if float(spread) <= 2 else "spread_gt_2c")
    ceiling = row["ceiling_ft"]
    result.append("no_numeric_ceiling" if ceiling == "" else "ceiling_500_999" if float(ceiling) < 1000 else "ceiling_ge_1000")
    change = row["ceiling_change_1h_ft"]
    if change != "" and float(change) <= -500:
        result.append("ceiling_falling_ge_500ft_per_hour")
    result.append("wind_missing" if row["wind_speed_kt"] == "" else
                  "wind_le_5kt" if float(row["wind_speed_kt"]) <= 5 else "wind_gt_5kt")
    return result


def main():
    folder = Path("data/processed/research")
    rows, y = load_dataset(folder)
    bundle = joblib.load("models/ceiling-risk-v2.joblib")
    meta = bundle["metadata"]
    ix = split_indices(rows, "2024-01-01", "2025-01-01", 24)
    p = adjusted(bundle["pipeline"].predict_proba(matrix(rows, meta["columns"])[ix])[:, 1], meta["offset"])
    rows = [rows[i] for i in ix]; y = y[ix]
    threshold = meta["threshold"]
    groups = sorted(set(g for row in rows for g in regimes(row)))
    strata = {}
    for group in groups:
        select = np.array([group in regimes(row) for row in rows])
        strata[group] = scores(y[select], p[select], threshold)
    cases = []
    for i, row in enumerate(rows):
        alarm = p[i] >= threshold
        if alarm == bool(y[i]):
            continue
        cases.append(dict(time=row["time"], error="false_alarm" if alarm else "miss",
            probability=float(p[i]), target=int(y[i]),
            **{key: row[key] for key in ["observation_time", "ceiling_ft", "ceiling_state",
                "visibility_m", "spread_c", "wind_speed_kt", "weather", "ceiling_change_1h_ft"]}))
    monthly = {str(month): dict(Counter(c["error"] for c in cases if int(c["time"][5:7]) == month))
               for month in range(1, 13)}
    write_csv(folder/"development-error-cases.csv", cases)
    report = dict(period="2024; calibration and threshold development, not independent validation",
        model=meta["selected"], threshold=threshold, overall=scores(y,p,threshold),
        strata=strata, monthly_error_origins=monthly,
        limitations="Strata overlap. Descriptive associations, not causal explanations. Origins are correlated. No threshold/model retuning.")
    write_json(Path("reports/development-error-audit.json"), report)
    print(strata)


if __name__ == "__main__":
    main()
