"""Create reproducible visual-summary data for the frozen GFS experiment."""
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import brier_score_loss

from .model import adjusted, matrix, split_indices
from .model_gfs import GFS, matched_dataset
from .pipeline import write_json


def group(name):
    if name.startswith("gfs_"):
        return "GFS 3 saatlik değişim" if name.endswith("change_3h") else "GFS mevcut tahmin"
    if name in {"hour_sin", "hour_cos", "year_sin", "year_cos"}:
        return "Zaman ve mevsim"
    if "change" in name or name == "recent_low_fraction":
        return "METAR eğilimleri"
    return "Mevcut LTFJ METAR"


def main():
    folder = Path("data/processed/research")
    _, _, rows, y = matched_dataset(folder)
    artifact = joblib.load("models/ceiling-risk-gfs.joblib")
    meta = artifact["metadata"]["matched_local_gfs"]
    model = artifact["models"]["matched_local_gfs"]
    indices = split_indices(rows, "2024-01-01", "2025-01-01", 24)
    x = matrix(rows, meta["columns"])[indices]
    yy = y[indices]
    base = adjusted(model.predict_proba(x)[:, 1], meta["offset"])
    base_brier = brier_score_loss(yy, base)
    rng = np.random.default_rng(20261001)
    importance = []
    for column, name in enumerate(meta["columns"]):
        increases = []
        for _ in range(5):
            changed = x.copy()
            changed[:, column] = rng.permutation(changed[:, column])
            probability = adjusted(model.predict_proba(changed)[:, 1], meta["offset"])
            increases.append(brier_score_loss(yy, probability) - base_brier)
        importance.append({"feature": name, "group": group(name),
                           "mean_brier_increase": float(np.mean(increases)),
                           "std_brier_increase": float(np.std(increases))})
    importance.sort(key=lambda item: item["mean_brier_increase"], reverse=True)
    results = json.loads(Path("reports/model-gfs-results.json").read_text())
    live_path = Path("data/processed/prospective/predictions.jsonl")
    live = json.loads(live_path.read_text().splitlines()[-1]) if live_path.exists() else None
    output = {"feature_counts": {name: sum(group(column) == name for column in meta["columns"])
                                 for name in ["Mevcut LTFJ METAR", "METAR eğilimleri", "Zaman ve mevsim",
                                              "GFS mevcut tahmin", "GFS 3 saatlik değişim"]},
              "total_features": len(meta["columns"]), "gfs_features": len(GFS),
              "permutation_importance_2024": importance,
              "importance_note": "2024 geliştirme döneminde tek değişken permütasyonu; nedensel etki değildir ve ilişkili girdiler önemi paylaşabilir.",
              "performance": results["results"], "thresholds": {k: v["threshold"] for k, v in artifact["metadata"].items()},
              "latest_live_prediction": live}
    write_json(Path("reports/model-gfs-visual-data.json"), output)
    print(json.dumps({"top_features": importance[:10], "live": live}, indent=2))


if __name__ == "__main__":
    main()
