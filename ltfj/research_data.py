"""Merge raw observations conservatively and construct a reproducible research set."""

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from datetime import timedelta
import io
import json
import math
from pathlib import Path
import re

from .adequacy import verified_load
from .metar import observation_body, parse
from .pipeline import build_rows, iso, timestamp, write_csv, write_json
from .sources import verified

NEIGHBORS = ("LTBA", "LTFM", "LTBQ", "LTBR")


def extract_raw(remarks):
    match = re.search(r"(?:METAR|SPECI)\s+(?:COR\s+)?LTFJ\b[^=]*", remarks)
    if not match:
        match = re.search(r"\bLTFJ\s+\d{6}Z\b[^=]*", remarks)
    return match.group() if match else None


def decoded(raw, t, station):
    result = parse(raw, station)
    if t.strftime("%d%H%MZ") not in observation_body(raw)[:5]:
        result = parse("")
        result["ceiling_state"] = "timestamp_mismatch"
    return result


def consensus(versions):
    """Agree field by field. Conflicting known values become missing, never pick a winner."""
    result, disagreements = {}, []
    for field in parse(""):
        values = {v[field] for v in versions if v[field] is not None}
        result[field] = next(iter(values)) if len(values) == 1 else None
        if len(values) > 1:
            disagreements.append(field)
    if "below_500" in disagreements:
        result.update(ceiling_ft=None, ceiling_state="source_conflict", below_500=None)
    elif "ceiling_state" in disagreements or "ceiling_ft" in disagreements:
        result["ceiling_state"] = "source_height_conflict"
        result["ceiling_ft"] = None
    return result, disagreements


def add_records(groups, rows, source, station="LTFJ"):
    for row in rows:
        if row["station"] != station:
            continue
        t = timestamp(row["valid"])
        groups[t].append((source, decoded(row["metar"], t, station)))


def finish(groups):
    observations, conflicts = [], Counter()
    for t, versions in sorted(groups.items()):
        result, differences = consensus([v for _, v in versions])
        conflicts.update(differences)
        observations.append(dict(time=t, **result, sources="+".join(sorted({s for s, _ in versions})),
                                 conflicting_fields=" ".join(differences)))
    return observations, conflicts


def load_sources(end):
    groups, metadata = defaultdict(list), []
    for filename in ["LTFJ_2020_2024.csv", "LTFJ_2025.csv"]:
        rows, meta = verified_load(Path("data/raw")/filename)
        metadata.append(meta)
        add_records(groups, rows, "IEM")
    text, meta = verified(Path("data/raw/LTFJ_2026.csv"))
    metadata.append(meta)
    add_records(groups, csv.DictReader(io.StringIO(text)), "IEM")
    ghcnh_counts = {}
    for year in range(2021, 2027):
        text, meta = verified(Path(f"data/raw/GHCNh_LTFJ_{year}.psv"))
        metadata.append(meta)
        counts = Counter()
        for row in csv.DictReader(io.StringIO(text), delimiter="|"):
            if row["STATION"] != "TUI0000LTFJ":
                raise ValueError("Unexpected GHCNh station")
            counts["all_rows"] += 1
            raw = extract_raw(row.get("REM", ""))
            if not raw:
                counts["no_raw_metar"] += 1
                continue
            t = timestamp(row["DATE"])
            if t >= end:
                continue
            counts["raw_metar"] += 1
            counts["explicit_speci"] += raw.startswith("SPECI")
            counts["source_fm16"] += row.get("REM_Report_Type") == "FM16"
            groups[t].append(("GHCNh", decoded(raw, t, "LTFJ")))
        ghcnh_counts[str(year)] = dict(counts)
    observations, conflicts = finish(groups)
    observations = [o for o in observations if timestamp("2021-01-01") <= o["time"] < end]
    return observations, dict(sources=metadata, ghcnh_counts=ghcnh_counts,
                              conflicting_fields=dict(conflicts))


def neighbor_data():
    text, meta = verified(Path("data/raw/neighbors_2021_2026.csv"))
    rows = list(csv.DictReader(io.StringIO(text)))
    result, counts = {}, {}
    for station in NEIGHBORS:
        groups = defaultdict(list)
        add_records(groups, rows, "IEM", station)
        result[station], _ = finish(groups)
        counts[station] = len(result[station])
    return result, dict(source=meta, counts=counts)


def asof(observations, times, cutoff, age_limit=60):
    i = bisect_right(times, cutoff)
    if not i:
        return None
    o = observations[i-1]
    return o if cutoff-o["time"] <= timedelta(minutes=age_limit) else None


def engineer(features, observations, neighbors, delay):
    times = [o["time"] for o in observations]
    ntimes = {s: [o["time"] for o in v] for s, v in neighbors.items()}
    for f in features:
        t = timestamp(f["time"])
        cutoff = t-timedelta(minutes=delay)
        c = f["ceiling_ft"]
        f["log_ceiling"] = math.log1p(c) if c is not None else None
        f["no_ceiling"] = int(f["ceiling_state"] == "no_ceiling_reported")
        v = f["visibility_m"]
        f["log_visibility"] = math.log1p(v) if v is not None else None
        direction, speed = f["wind_direction_deg"], f["wind_speed_kt"]
        for axis in ["u", "v"]:
            f["wind_"+axis] = (-speed * (math.sin if axis == "u" else math.cos)(math.radians(direction))
                                  if direction is not None and speed is not None else None)
        f["fog_mist"] = int(any(x in (f["weather"] or "") for x in ["FG", "BR"]))
        f["rain"] = int(any(x in (f["weather"] or "") for x in ["RA", "DZ"]))
        f["hour_sin"], f["hour_cos"] = math.sin(2*math.pi*f["hour_utc"]/24), math.cos(2*math.pi*f["hour_utc"]/24)
        angle = 2*math.pi*(t.timetuple().tm_yday-1)/365.25
        f["year_sin"], f["year_cos"] = math.sin(angle), math.cos(angle)
        for hours in [1, 3]:
            past = asof(observations, times, cutoff-timedelta(hours=hours), 35)
            for source, name in [("qnh_hpa", "pressure"), ("spread_c", "spread"),
                                 ("visibility_m", "visibility")]:
                f[f"{name}_change_{hours}h"] = (f[source]-past[source]
                    if past and f[source] is not None and past[source] is not None else None)
        window = observations[bisect_right(times, cutoff-timedelta(hours=3)):bisect_right(times, cutoff)]
        f["recent_low_fraction"] = (sum(o["below_500"] is True for o in window)/len(window) if window else None)
        for station, data in neighbors.items():
            o = asof(data, ntimes[station], cutoff, 60)
            for key in ["spread_c", "visibility_m", "ceiling_ft", "qnh_hpa"]:
                value = o[key] if o else None
                f[f"{station}_{key}"] = (math.log1p(value) if value is not None and key in
                                          {"visibility_m", "ceiling_ft"} else value)
            f[f"{station}_no_ceiling"] = int(o["ceiling_state"] == "no_ceiling_reported") if o else None
            f[f"{station}_age"] = (t-o["time"]).total_seconds()/60 if o else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", default="2026-09-21", type=timestamp)
    parser.add_argument("--delay", default=10, type=int)
    parser.add_argument("--output", default=Path("data/processed/research"), type=Path)
    args = parser.parse_args()
    observations, audit = load_sources(args.end)
    neighbors, naudit = neighbor_data()
    features, labels = build_rows(observations, timestamp("2021-01-01"), args.end, args.delay)
    engineer(features, observations, neighbors, args.delay)
    write_csv(args.output/"features.csv", features)
    write_csv(args.output/"labels.csv", labels)
    write_csv(args.output/"observations.csv", [dict(o, time=iso(o["time"])) for o in observations])
    audit.update(neighbors=naudit, assumed_delay_minutes=args.delay, end_exclusive=iso(args.end),
                 note="Receipt times unknown. Delay is an explicit assumption, not verified availability.",
                 observation_counts_by_year=dict(Counter(o["time"].year for o in observations)),
                 sources_by_year={str(y):dict(Counter(o["sources"] for o in observations if o["time"].year==y))
                                  for y in range(2021,2027)},
                 labels_by_year={str(y):dict(Counter(l["label_status"] for l in labels if l["time"].startswith(str(y))))
                                 for y in range(2021,2027)})
    write_json(Path("reports/research-data-audit.json"), audit)
    print(json.dumps({"observations":len(observations), "ghcnh":audit["ghcnh_counts"],
                      "conflicts":audit["conflicting_fields"],"neighbors":naudit["counts"]},indent=2))


if __name__ == "__main__":
    main()
