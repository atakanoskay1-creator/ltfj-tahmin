"""Frozen chronological logistic-regression experiment; no random row splits."""

import argparse
from bisect import bisect_left, bisect_right
from collections import defaultdict
import csv
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import warnings

import joblib
import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, precision_recall_curve, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .adequacy import runs
from .pipeline import timestamp, write_csv, write_json
from .research_data import NEIGHBORS

LOCAL = ["log_ceiling", "no_ceiling", "spread_c", "temperature_c", "log_visibility",
         "wind_u", "wind_v", "wind_speed_kt", "qnh_hpa", "fog_mist", "rain",
         "hour_sin", "hour_cos", "year_sin", "year_cos", "ceiling_change_1h_ft",
         "pressure_change_1h", "pressure_change_3h", "spread_change_1h", "spread_change_3h",
         "visibility_change_1h", "visibility_change_3h", "recent_low_fraction"]
NEIGHBOR = [f"{s}_{k}" for s in NEIGHBORS for k in
            ["spread_c", "visibility_m", "ceiling_ft", "no_ceiling", "age"]]


def matrix(rows, columns):
    return np.array([[float(r[c]) if r[c] not in ("", None) else np.nan for c in columns] for r in rows])


def split_indices(rows, start, end, embargo_hours=0):
    start, end = timestamp(start), timestamp(end)-timedelta(hours=embargo_hours)
    return np.array([i for i,r in enumerate(rows) if start <= timestamp(r["time"]) < end
                     and timestamp(r["target_end"]) < end], dtype=int)


def calibrate_offset(y, probabilities):
    if len(set(y)) != 2:
        raise ValueError("Calibration period must contain both outcomes")
    z = logit(np.clip(probabilities, 1e-8, 1-1e-8))
    return float(brentq(lambda offset: np.mean(expit(z+offset))-np.mean(y), -30, 30))


def adjusted(p, offset):
    return expit(logit(np.clip(p, 1e-8, 1-1e-8))+offset)


def alarm_threshold(y, probabilities, recall_goal=.70):
    precision, recall, thresholds = precision_recall_curve(y, probabilities)
    allowed = np.flatnonzero(recall[:-1] >= recall_goal)
    if not len(allowed):
        raise ValueError("No feasible alarm threshold")
    best = max(allowed, key=lambda i: (precision[i], thresholds[i]))
    return float(thresholds[best])


def scores(y, p, threshold=None):
    result = dict(n=int(len(y)), positives=int(sum(y)), prevalence=float(np.mean(y)),
                  brier=float(brier_score_loss(y,p)), log_loss=float(log_loss(y,p,labels=[0,1])),
                  average_precision=float(average_precision_score(y,p)) if sum(y) else None,
                  roc_auc=float(roc_auc_score(y,p)) if len(set(y))==2 else None,
                  mean_probability=float(np.mean(p)))
    if threshold is not None:
        alarm = p >= threshold
        tp, fp = int(sum(alarm & (y==1))), int(sum(alarm & (y==0)))
        fn, tn = int(sum(~alarm & (y==1))), int(sum(~alarm & (y==0)))
        result.update(threshold=threshold, tp=tp, fp=fp, fn=fn, tn=tn,
                      recall=tp/(tp+fn) if tp+fn else None,
                      precision=tp/(tp+fp) if tp+fp else None,
                      false_alarm_ratio=fp/(tp+fp) if tp+fp else None,
                      false_positive_rate=fp/(fp+tn) if fp+tn else None,
                      alarm_origin_fraction=float(np.mean(alarm)))
    return result


def block_intervals(y, p, reference, times, threshold, repetitions=500):
    blocks = defaultdict(list)
    origin = min(times).replace(hour=0,minute=0,second=0,microsecond=0)
    for i,t in enumerate(times):
        blocks[(t-origin).days//7].append(i)
    blocks = [np.array(v) for v in blocks.values()]
    rng = np.random.default_rng(20260921)
    samples = defaultdict(list)
    for _ in range(repetitions):
        indices = np.concatenate([blocks[i] for i in rng.integers(0,len(blocks),len(blocks))])
        yy, pp, rr = y[indices], p[indices], reference[indices]
        if sum(yy)==0:
            continue
        ref = np.mean((yy-rr)**2)
        samples["brier_skill"].append(1-np.mean((yy-pp)**2)/ref)
        samples["average_precision"].append(average_precision_score(yy,pp))
        alarm=pp>=threshold
        samples["recall"].append(sum(alarm & (yy==1))/sum(yy))
        if sum(alarm):
            samples["precision"].append(sum(alarm & (yy==1))/sum(alarm))
    return dict(method="paired non-overlapping 7-day blocks; percentile 95% intervals",
                blocks=len(blocks), resamples=repetitions,
                intervals={k:[float(x) for x in np.quantile(v,[.025,.975])] for k,v in samples.items()})


def event_scores(observations, times, probabilities, threshold, start, end):
    episodes = [e for e in runs(observations) if timestamp(start)<=timestamp(e["start"])<timestamp(end)]
    eligible, detected, lead = 0,0,[]
    for e in episodes:
        onset=timestamp(e["start"])
        left,right=bisect_left(times,onset-timedelta(hours=3)),bisect_left(times,onset)
        if left==right:
            continue
        eligible+=1
        alarms=[times[i] for i in range(left,right) if probabilities[i]>=threshold]
        if alarms:
            detected+=1
            lead.append((onset-min(alarms)).total_seconds()/60)
    return dict(observed_low_runs=len(episodes), runs_with_eligible_origin=eligible,
                detected_runs=detected, recall=detected/eligible if eligible else None,
                median_first_alarm_lead_minutes=float(np.median(lead)) if lead else None,
                note="Runs are not independent weather events; lead time is to first observed low report.")


def climatology(rows, train_indices, y):
    global_rate=float((sum(y[train_indices])+1)/(len(train_indices)+2))
    buckets=defaultdict(lambda:[0,0])
    for i in train_indices:
        key=(int(rows[i]["month"]),int(float(rows[i]["hour_utc"]))//6)
        buckets[key][0]+=int(y[i]); buckets[key][1]+=1
    return np.array([(buckets[(int(r["month"]),int(float(r["hour_utc"]))//6)][0]+200*global_rate)/
                     (buckets[(int(r["month"]),int(float(r["hour_utc"]))//6)][1]+200) for r in rows])


def current_ceiling_baseline(rows, train_indices, y):
    def bucket(r):
        c=float(r["ceiling_ft"]) if r["ceiling_ft"] else None
        return "absent" if c is None else "under1000" if c<1000 else "under3000" if c<3000 else "high"
    rate=float((sum(y[train_indices])+1)/(len(train_indices)+2))
    groups=defaultdict(lambda:[0,0])
    for i in train_indices:
        groups[bucket(rows[i])][0]+=int(y[i]);groups[bucket(rows[i])][1]+=1
    return np.array([(groups[bucket(r)][0]+50*rate)/(groups[bucket(r)][1]+50) for r in rows])


def load_dataset(folder):
    with (folder/"features.csv").open(encoding="utf-8") as handle:
        features=list(csv.DictReader(handle))
    with (folder/"labels.csv").open(encoding="utf-8") as handle:
        labels=list(csv.DictReader(handle))
    if len(features)!=len(labels) or any(f["time"]!=l["time"] for f,l in zip(features,labels)):
        raise ValueError("Feature/label alignment mismatch")
    rows=[dict(f,**l) for f,l in zip(features,labels) if l["below_500_within_3h"] in {"0","1"}]
    return rows,np.array([int(r["below_500_within_3h"]) for r in rows])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=Path("data/processed/research"))
    args=parser.parse_args()
    protocol=json.loads(Path("research-protocol.json").read_text(encoding="utf-8"))
    rows,y=load_dataset(args.data)
    train=split_indices(rows,*protocol["development_train"],protocol["boundary_embargo_hours"])
    validation=split_indices(rows,*protocol["development_validation"],protocol["boundary_embargo_hours"])
    feature_sets={"local":LOCAL,"local_and_neighbors":LOCAL+NEIGHBOR}
    candidates=[]; fitted={}
    warnings.filterwarnings("error",category=ConvergenceWarning)
    for name,columns in feature_sets.items():
        x=matrix(rows,columns)
        for c in protocol["regularization_candidates_C"]:
            pipe=make_pipeline(SimpleImputer(strategy="median",add_indicator=True,keep_empty_features=True),
                               StandardScaler(),LogisticRegression(C=c,max_iter=3000,tol=1e-7))
            pipe.fit(x[train],y[train])
            p=pipe.predict_proba(x[validation])[:,1]
            key=f"{name}_C{c}"
            fitted[key]=(pipe,columns)
            candidates.append(dict(name=key,feature_set=name,C=c,validation=scores(y[validation],p)))
            print(key,json.dumps(candidates[-1]["validation"]),flush=True)
    winner=min(candidates,key=lambda item:item["validation"]["brier"])
    pipe,columns=fitted[winner["name"]]
    raw=pipe.predict_proba(matrix(rows,columns))[:,1]
    offset=calibrate_offset(y[validation],raw[validation])
    calibrated=adjusted(raw,offset)
    threshold=alarm_threshold(y[validation],calibrated[validation])
    # Freeze every choice before computing either test's outcome metrics.
    frozen=dict(protocol=protocol,selected=winner,calibration_offset=offset,threshold=threshold,
                columns=columns,train_samples=len(train),validation_samples=len(validation),
                input_hashes={name:hashlib.sha256((args.data/name).read_bytes()).hexdigest()
                              for name in ["features.csv","labels.csv"]})
    write_json(Path("models/frozen-selection.json"),frozen)
    joblib.dump(dict(pipeline=pipe,columns=columns,offset=offset,threshold=threshold,metadata=frozen),
                "models/ceiling-risk.joblib")
    probability=float((sum(y[train])+1)/(len(train)+2))
    predictions={"constant":np.full(len(rows),probability), "season_hour":climatology(rows,train,y),
                 "current_ceiling":current_ceiling_baseline(rows,train,y),
                 "selected_raw":raw,"selected_calibrated":calibrated}
    for name in feature_sets:
        best=min([r for r in candidates if r["feature_set"]==name],key=lambda r:r["validation"]["brier"])
        model,cols=fitted[best["name"]]
        predictions[name]=model.predict_proba(matrix(rows,cols))[:,1]
    with (args.data/"observations.csv").open(encoding="utf-8") as handle:
        observations=[dict(time=timestamp(r["time"]),below_500={"True":True,"False":False}.get(r["below_500"]),
                           ceiling_ft=float(r["ceiling_ft"]) if r["ceiling_ft"] else None)
                      for r in csv.DictReader(handle)]
    results={}
    exports=[]
    for period,key in [("validation_2024","development_validation"),
                       ("test_2025","retrospective_test"),("test_2026","temporal_test")]:
        indices=split_indices(rows,*protocol[key],protocol["boundary_embargo_hours"] if period=="validation_2024" else 0)
        metrics={name:scores(y[indices],p[indices],threshold if name=="selected_calibrated" else None)
                 for name,p in predictions.items()}
        reference=predictions["constant"][indices]
        for item in metrics.values():
            item["brier_skill_vs_constant"]=1-item["brier"]/metrics["constant"]["brier"]
        times=[timestamp(rows[i]["time"]) for i in indices]
        results[period]=dict(metrics=metrics,
            events=event_scores(observations,times,calibrated[indices],threshold,*protocol[key]))
        if period.startswith("test"):
            results[period]["uncertainty"]=block_intervals(y[indices],calibrated[indices],reference,times,threshold)
        for i in indices:
            exports.append(dict(time=rows[i]["time"],period=period,target=int(y[i]),
                                **{name:float(p[i]) for name,p in predictions.items()}))
        print(period,json.dumps(results[period]),flush=True)
    write_csv(args.data/"predictions.csv",exports)
    feature_names=pipe[0].get_feature_names_out(columns)
    coefficients=sorted([dict(feature=str(n),standardized_log_odds=float(c))
                         for n,c in zip(feature_names,pipe[-1].coef_[0])],
                        key=lambda r:abs(r["standardized_log_odds"]),reverse=True)
    report=dict(frozen_selection=frozen,candidates=candidates,results=results,
                coefficients=coefficients,coefficient_note="Associations, not causal effects; correlated inputs complicate interpretation.")
    write_json(Path("reports/model-results.json"),report)


if __name__ == "__main__":
    main()
