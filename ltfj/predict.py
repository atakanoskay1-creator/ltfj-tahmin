"""Evaluate saved research coefficients on an existing prepared historical row."""

import argparse
import csv
import json
import math
from pathlib import Path

from .pipeline import iso, timestamp


def probability(row, parameters):
    missing=[row[c] in ("",None) for c in parameters["columns"]]
    values=[parameters["imputation"][i] if missing[i] else float(row[c])
            for i,c in enumerate(parameters["columns"])]
    values.extend(float(missing[i]) for i in parameters["missing_indicator_indices"])
    z=parameters["intercept"]+sum(coef*(value-mean)/scale for value,mean,scale,coef in
        zip(values,parameters["mean"],parameters["scale"],parameters["coefficients"],strict=True))
    raw=1/(1+math.exp(-max(-700,min(700,z))))
    raw=min(1-1e-8,max(1e-8,raw))
    z=math.log(raw/(1-raw))+parameters["calibration_offset"]
    return 1/(1+math.exp(-max(-700,min(700,z))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at",required=True,type=timestamp)
    parser.add_argument("--features",type=Path,default=Path("data/processed/research/features.csv"))
    parser.add_argument("--parameters",type=Path,default=Path("reports/model-parameters.json"))
    args=parser.parse_args()
    parameters=json.loads(args.parameters.read_text(encoding="utf-8"))
    with args.features.open(encoding="utf-8") as handle:
        row=next((r for r in csv.DictReader(handle) if timestamp(r["time"])==args.at),None)
    if row is None:
        raise ValueError("Requested time is absent from prepared historical features")
    status="research_estimate"
    p=None
    if row["below_500"]=="True":
        status="already_below_threshold"
    elif row["below_500"]!="False" or not row["observation_age_minutes"] or float(row["observation_age_minutes"])>35:
        status="insufficient_current_observation"
    else:
        p=probability(row,parameters)
    print(json.dumps(dict(time=iso(args.at),status=status,probability=p,
                         threshold_exceeded=p>=parameters["experimental_threshold"] if p is not None else None,
                         note="Historical research estimate; not a live weather forecast."),indent=2))


if __name__ == "__main__":
    main()
