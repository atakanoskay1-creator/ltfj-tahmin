"""Reproducible data sufficiency audit; no fitted model or skill claims."""

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import re
from statistics import median

from .metar import observation_body, parse
from .pipeline import (MAX_GAP, build_rows, iso, load_observations,
                       read_csv, target, timestamp, write_json)


def verified_load(path):
    payload = path.read_bytes()
    manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(payload).hexdigest() != manifest["sha256"]:
        raise ValueError(f"Checksum mismatch: {path}")
    return read_csv(payload.decode("utf-8-sig")), manifest


def runs(observations):
    result = []
    active = None
    previous = None
    for o in observations:
        if o["below_500"] is True:
            if active is None or previous is None or o["time"] - previous > MAX_GAP:
                active = dict(start=iso(o["time"]), end=iso(o["time"]), count=0,
                              minimum_ft=o["ceiling_ft"])
                result.append(active)
            active["end"] = iso(o["time"])
            active["count"] += 1
            if o["ceiling_ft"] is not None:
                active["minimum_ft"] = min(active["minimum_ft"] or o["ceiling_ft"], o["ceiling_ft"])
        else:
            active = None
        previous = o["time"]
    return result


def summarize(observations, year):
    start, end = timestamp(f"{year}-01-01"), timestamp(f"{year+1}-01-01")
    data = [o for o in observations if start <= o["time"] < end]
    features, labels = build_rows(data, start, end)
    episodes = runs(data)
    low = [o for o in data if o["below_500"] is True]
    expected = int((end-start).total_seconds()/1800)
    grid = {start + timedelta(minutes=20+30*i) for i in range(expected)}
    observed_times = {o["time"] for o in data}
    gaps = [dict(start=iso(a["time"]), end=iso(b["time"]),
                 minutes=(b["time"]-a["time"]).total_seconds()/60)
            for a, b in zip(data, data[1:]) if b["time"] - a["time"] > MAX_GAP]
    monthly = {}
    for month in range(1, 13):
        prefix = f"{year}-{month:02}"
        monthly[prefix] = dict(
            observations=sum(o["time"].month == month for o in data),
            low_observations=sum(o["time"].month == month for o in low),
            low_runs=sum(e["start"].startswith(prefix) for e in episodes),
            positive_origins=sum(r["time"].startswith(prefix) and
                                 r["below_500_within_3h"] == 1 for r in labels))
    clusters = {}
    for hours in [6, 24]:
        clusters[str(hours)] = sum(i == 0 or timestamp(e["start"]) - timestamp(episodes[i-1]["end"])
                                  > timedelta(hours=hours) for i, e in enumerate(episodes))
    eligible = [(f, l) for f, l in zip(features, labels) if l["below_500_within_3h"] is not None]
    bins = defaultdict(Counter)
    for f, l in eligible:
        c = f["ceiling_ft"]
        key = ("500-900" if c is not None and c < 1000 else
               "1000-2900" if c is not None and c < 3000 else
               "3000+" if c is not None else f["ceiling_state"])
        bins[key]["origins"] += 1
        bins[key]["positives"] += l["below_500_within_3h"]
    return dict(observations=len(data), expected_half_hour_slots=expected,
                missing_routine_slots=len(grid-observed_times), off_grid_reports=len(observed_times-grid),
                low_observations=len(low), low_days=len({o["time"].date() for o in low}),
                low_runs=len(episodes), clusters_by_dry_gap_hours=clusters,
                single_report_runs=sum(e["count"] == 1 for e in episodes),
                median_run_observed_span_minutes=median((timestamp(e["end"])-timestamp(e["start"])).total_seconds()/60
                                                       for e in episodes) if episodes else None,
                largest_run_observations=max((e["count"] for e in episodes), default=0),
                ceiling_histogram_up_to_1500=dict(sorted(Counter(o["ceiling_ft"] for o in data
                    if o["ceiling_ft"] is not None and o["ceiling_ft"] <= 1500).items())),
                ceiling_states=dict(Counter(o["ceiling_state"] for o in data)),
                feature_null_counts={k: sum(o[k] is None for o in data)
                    for k in ["temperature_c", "dewpoint_c", "wind_speed_kt", "visibility_m", "qnh_hpa"]},
                impossible_spread_rows=sum(o["spread_c"] is not None and o["spread_c"] < 0 for o in data),
                label_counts=dict(Counter(r["label_status"] for r in labels)),
                current_ceiling_bins=dict(bins), monthly=monthly, gaps=gaps, episodes=episodes)


def compare_noaa(path, observations):
    payload = path.read_bytes()
    rows = list(csv.DictReader(payload.decode("utf-8-sig").splitlines()))
    if any(r["STATION"] != "17063099999" for r in rows):
        raise ValueError("Unexpected NOAA station")
    iem = {o["time"]: o for o in observations}
    counts = Counter()
    differences = []
    aviation_times = set()
    low_times = set()
    additions = []
    cig_examples = []
    missing_by_type = Counter()
    for row in rows:
        if row["REPORT_TYPE"].strip() not in {"FM-15", "FM-16"}:
            continue
        t = timestamp(row["DATE"])
        aviation_times.add(t)
        raw = re.search(r"(?:METAR|SPECI)\s+(?:COR\s+)?LTFJ\b.*", row.get("REM", ""))
        if raw:
            parsed = parse(raw.group())
            if t.strftime("%d%H%MZ") not in observation_body(raw.group())[:5]:
                raise ValueError("NOAA raw METAR timestamp mismatch")
            if parsed["below_500"] is True:
                low_times.add(t)
            if t not in iem:
                additions.append(dict(time=t, **parsed))
                if parsed["below_500"] is True:
                    counts["additional_low_observations"] += 1
            if t in iem:
                counts["matched_raw_ceiling_status"] += 1
                if parsed["below_500"] != iem[t]["below_500"] or parsed["ceiling_ft"] != iem[t]["ceiling_ft"]:
                    differences.append(dict(time=iso(t), iem_ft=iem[t]["ceiling_ft"],
                                            noaa_raw_ft=parsed["ceiling_ft"]))
        if t not in iem:
            counts["noaa_aviation_times_missing_from_iem"] += 1
            missing_by_type[row["REPORT_TYPE"].strip()] += 1
            continue
        height, quality, *_ = row["CIG"].split(",")
        # Compare numeric decoded heights only; 22000/99999 are not METAR heights.
        if quality in {"1", "5"} and height not in {"99999", "22000"} and iem[t]["ceiling_ft"] is not None:
            counts["matched_numeric_cig"] += 1
            if abs(int(height) - iem[t]["ceiling_ft"] * 0.3048) > 1.1:
                counts["numeric_cig_disagreement_over_1_1m"] += 1
                if len(cig_examples) < 5:
                    cig_examples.append(dict(time=iso(t), noaa_cig_m=int(height),
                                             raw_ceiling_ft=iem[t]["ceiling_ft"], raw=row["REM"]))
    first, last = min(aviation_times), max(aviation_times)
    overlap = {t for t in iem if first <= t <= last}
    # Sensitivity only: keep all IEM reports, add NOAA reports at missing times.
    # Do not silently replace training data with this partially enriched archive.
    base = [o for o in observations if o["time"].year == 2025]
    union = sorted(base + additions, key=lambda o: o["time"])
    start, end = timestamp("2025-01-01"), timestamp("2026-01-01")
    _, before = build_rows(base, start, end)
    _, after = build_rows(union, start, end)
    transitions = Counter(f'{a["label_status"]} -> {b["label_status"]}'
                          for a, b in zip(before, after) if a["label_status"] != b["label_status"])
    times, union_times = [o["time"] for o in base], [o["time"] for o in union]
    future_only_flips = []
    for label in before:
        if label["below_500_within_3h"] != 0:
            continue
        t = timestamp(label["time"])
        current = base[bisect_right(times, t)-1]
        future = union[bisect_right(union_times, t):bisect_right(union_times, t+timedelta(hours=3))]
        if target(current, future, t, end)[0] == 1:
            future_only_flips.append(iso(t))
    return dict(source_url="https://www.ncei.noaa.gov/data/global-hourly/access/2025/17063099999.csv",
                sha256=hashlib.sha256(payload).hexdigest(), rows=len(rows),
                report_types=dict(Counter(r["REPORT_TYPE"].strip() for r in rows)),
                first_aviation_report=iso(first), last_aviation_report=iso(last),
                unique_aviation_times=len(aviation_times), noaa_low_times=len(low_times),
                iem_times_absent_from_noaa_in_overlap=len(overlap-aviation_times),
                counts=dict(counts), missing_from_iem_by_type=dict(missing_by_type),
                raw_ceiling_differences=differences, cig_difference_examples=cig_examples,
                augmentation_sensitivity=dict(added_reports=len(additions),
                    added_low_reports=sum(o["below_500"] is True for o in additions),
                    merged_low_runs=len(runs(union)),
                    merged_label_counts=dict(Counter(r["label_status"] for r in after)),
                    label_status_changes=dict(transitions),
                    fixed_current_negative_to_positive_origins=future_only_flips),
                note="Different archive, partly shared upstream observations; not independent measurement.")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--inputs", nargs="+", type=Path, required=True)
    cli.add_argument("--noaa", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    all_rows, manifests = [], []
    for path in args.inputs:
        rows, manifest = verified_load(path)
        all_rows.extend(rows)
        manifests.append(manifest)
    observations, counts = load_observations(all_rows)
    years = {str(year): summarize(observations, year)
             for year in sorted({o["time"].year for o in observations})}
    result = dict(sources=manifests, combined_counts=dict(counts), years=years,
                  noaa_comparison=compare_noaa(args.noaa, observations),
                  notes=["Yearly label windows are censored at each year boundary.",
                         "Run/cluster counts are descriptive, not proven independent events.",
                         "Observed run span excludes uncertain onset/termination between reports."])
    write_json(args.output, result)
    for year, data in years.items():
        print(year, json.dumps({k: data[k] for k in ["observations", "missing_routine_slots",
              "off_grid_reports", "low_observations", "low_days", "low_runs",
              "clusters_by_dry_gap_hours", "single_report_runs", "label_counts"]}))
    print(json.dumps(result["noaa_comparison"], indent=2))


if __name__ == "__main__":
    main()
