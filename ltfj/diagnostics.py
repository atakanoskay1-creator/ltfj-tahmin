"""Post-fit diagnostics with frozen model choices; never refits to test outcomes."""

import csv
from datetime import timedelta
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/processed/matplotlib-cache").resolve()))

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import precision_recall_curve

from .metar import parse
from .model import adjusted, matrix, scores
from .pipeline import build_rows, timestamp, write_json
from .research_data import engineer, neighbor_data


def main():
    folder=Path("data/processed/research")
    report=json.loads(Path("reports/model-results.json").read_text(encoding="utf-8"))
    bundle=joblib.load("models/ceiling-risk.joblib")
    pipe=bundle["pipeline"]
    parameters=dict(columns=bundle["columns"],
        imputation=[float(x) for x in pipe[0].statistics_],
        missing_indicator_indices=[int(x) for x in pipe[0].indicator_.features_],
        mean=[float(x) for x in pipe[1].mean_],scale=[float(x) for x in pipe[1].scale_],
        coefficients=[float(x) for x in pipe[-1].coef_[0]], intercept=float(pipe[-1].intercept_[0]),
        calibration_offset=bundle["offset"], experimental_threshold=bundle["threshold"],
        metadata=bundle["metadata"], status="research_only")
    write_json(Path("reports/model-parameters.json"),parameters)
    with (folder/"predictions.csv").open(encoding="utf-8") as handle:
        predictions=list(csv.DictReader(handle))
    diagnostics={"fixed_thresholds":{},"reliability":{}}
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout="constrained")
    colors={"selected_calibrated":"#167d9a","local":"#be7040","constant":"#777777"}
    for col,period in enumerate(["test_2025","test_2026"]):
        rows=[r for r in predictions if r["period"]==period]
        y=np.array([int(r["target"]) for r in rows]);p=np.array([float(r["selected_calibrated"]) for r in rows])
        diagnostics["fixed_thresholds"][period]={str(t):scores(y,p,t) for t in [.025,.05,.1,.2]}
        bins=[]
        edges=[0,.005,.01,.025,.05,.1,.2,1.0001]
        for left,right in zip(edges,edges[1:]):
            mask=(p>=left)&(p<right)
            if mask.any():
                bins.append(dict(lower=left,upper=right,n=int(sum(mask)),
                                 mean_probability=float(np.mean(p[mask])),observed_rate=float(np.mean(y[mask]))))
        diagnostics["reliability"][period]=bins
        ax=axes[0,col]
        ax.plot([0,.5],[0,.5],"--",color="#999999",label="Tam uyum")
        ax.plot([b["mean_probability"] for b in bins],[b["observed_rate"] for b in bins],"o-",color=colors["selected_calibrated"])
        for b in bins:
            if b["mean_probability"] >= .025:
                ax.annotate("n="+str(b["n"]),(b["mean_probability"],b["observed_rate"]),xytext=(4,5),textcoords="offset points",fontsize=8)
        ax.set(xlim=(0,.5),ylim=(0,.5),xlabel="Tahmin edilen olasılık",ylabel="Gözlenen olay oranı",
               title=f"{period[-4:]}: olasılık tutarlılığı")
        ax=axes[1,col]
        for name in ["selected_calibrated","local"]:
            pr,rec,_=precision_recall_curve(y,np.array([float(r[name]) for r in rows]))
            ax.plot(rec,pr,color=colors[name],label="Seçilen + komşular" if name=="selected_calibrated" else "Yalnızca LTFJ")
        ax.axhline(float(np.mean(y)),linestyle="--",color="#999999",label="Olay sıklığı")
        metric=report["results"][period]["metrics"]["selected_calibrated"]
        ax.scatter([metric["recall"]],[metric["precision"]],color="#b52f3d",zorder=4,label="2024'te seçilen eşik")
        ax.set(xlim=(0,1),ylim=(0,1),xlabel="Pozitif tahmin zamanlarını yakalama oranı",ylabel="Uyarıların isabet oranı",
               title=f"{period[-4:]}: yakalama / yanlış alarm dengesi")
        ax.legend(fontsize=8)
    for ax in axes.flat:
        ax.grid(alpha=.18)
    fig.suptitle("LTFJ • 3 saat içinde <500 ft | Sabitlenmiş model değerlendirmesi",fontsize=15)
    fig.savefig("reports/model-diagnostics.png",dpi=160)
    plt.close(fig)
    # Latency sensitivity: same frozen model, all scheduled test origins retained for coverage.
    with (folder/"observations.csv").open(encoding="utf-8") as handle:
        raw=list(csv.DictReader(handle))
    observations=[]
    for r in raw:
        o={"time":timestamp(r["time"])}
        for key in parse(""):
            value=r[key]
            o[key]=(None if value=="" and key!="weather" else
                    {"True":True,"False":False}.get(value) if key in {"below_500","corrected","visibility_lower_bound"}
                    else value if key in {"ceiling_state","weather"} else float(value))
        observations.append(o)
    neighbors,_=neighbor_data()
    latency={}
    for delay in [0,10,20]:
        start,end=timestamp("2025-01-01"),timestamp("2026-09-21")
        features,labels=build_rows(observations,start,end,delay)
        engineer(features,observations,neighbors,delay)
        for year in [2025,2026]:
            pairs=[(f,l) for f,l in zip(features,labels) if f["time"].startswith(str(year))]
            eligible=[(f,l) for f,l in pairs if l["below_500_within_3h"] in [0,1]]
            f=[a for a,_ in eligible];y=np.array([b["below_500_within_3h"] for _,b in eligible])
            p=adjusted(pipe.predict_proba(matrix(f,bundle["columns"]))[:,1],bundle["offset"])
            latency[f"{year}_delay_{delay}"]=dict(scheduled_origins=len(pairs),scored_origins=len(eligible),
                coverage_fraction=len(eligible)/len(pairs),metrics=scores(y,p,bundle["threshold"]))
        print(f"Latency diagnostic complete: {delay} minutes",flush=True)
    diagnostics["latency"]=latency
    diagnostics["latency_note"]="Coverage includes already-low/unknown exclusions; differing eligible sets prevent direct skill comparison. No refitting."
    write_json(Path("reports/model-diagnostics.json"),diagnostics)


if __name__ == "__main__":
    main()
