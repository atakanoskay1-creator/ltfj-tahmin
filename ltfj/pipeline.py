"""Download, audit and label archival observations. All timestamps are UTC."""

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .metar import observation_body, parse

UTC = timezone.utc
HORIZON = timedelta(hours=3)
STEP = timedelta(minutes=30)
MAX_GAP = timedelta(minutes=35)
MAX_AGE = timedelta(minutes=35)


def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    if not {"station", "valid", "metar"}.issubset(reader.fieldnames or []):
        raise ValueError("Expected IEM CSV columns: station, valid, metar")
    return list(reader)


def fetch(start, end, output):
    if start >= end:
        raise ValueError("Start must precede exclusive end")
    if output.exists() or output.with_suffix(".manifest.json").exists():
        raise FileExistsError(f"Refusing to replace existing source: {output}")
    params = dict(station="LTFJ", data="metar", sts=iso(start), ets=iso(end),
                  tz="Etc/UTC", format="onlycomma", latlon="no", elev="no",
                  missing="M", direct="no", report_type="3,4")
    url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "ltfj-tahmin/0.1 (historical research)"})
    with urlopen(request, timeout=120) as response:
        payload = response.read()
    rows = read_csv(payload.decode("utf-8-sig"))
    if not rows:
        raise ValueError("Source returned no observations")
    for row in rows:
        if row["station"] != "LTFJ" or not start <= timestamp(row["valid"]) < end:
            raise ValueError("Source returned wrong station or out-of-range timestamp")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    write_json(output.with_suffix(".manifest.json"), dict(
        source_url=url, station="LTFJ", start=iso(start), end_exclusive=iso(end),
        retrieved_at=iso(datetime.now(UTC)), rows=len(rows),
        sha256=hashlib.sha256(payload).hexdigest(),
        source_terms="https://mesonet.agron.iastate.edu/disclaimer.php"))
    print(f"Downloaded {len(rows)} observations to {output}")


def load_observations(rows):
    groups = defaultdict(dict)
    counts = Counter()
    for row in rows:
        counts["input_rows"] += 1
        if row["station"] != "LTFJ":
            raise ValueError("Only LTFJ input is supported")
        time = timestamp(row["valid"])
        raw = " ".join(row["metar"].split())
        if raw in groups[time]:
            counts["exact_duplicates"] += 1
        parsed = parse(raw)
        if time.strftime("%d%H%MZ") not in observation_body(raw)[:5]:
            parsed = parse("")
            parsed["ceiling_state"] = "timestamp_mismatch"
            counts["timestamp_mismatch_rows"] += 1
        groups[time][raw] = parsed
    observations = []
    for time, versions in sorted(groups.items()):
        if len(versions) > 1:
            # Archive has no receipt/version times: do not guess which was available.
            parsed = parse("")
            parsed["ceiling_state"] = "conflicting_reports"
            counts["conflicting_timestamps"] += 1
        else:
            parsed = next(iter(versions.values())).copy()
        observations.append(dict(time=time, **parsed))
    counts["unique_timestamps"] = len(observations)
    return observations, counts


def target(current, future, t, archive_end):
    if current is None or t - current["time"] > MAX_AGE:
        return None, "missing_current"
    if current["below_500"] is True:
        return None, "already_below_threshold"
    if current["below_500"] is None:
        return None, "unknown_current"
    if any(o["below_500"] is True for o in future):
        return 1, "event"
    if t + HORIZON >= archive_end:
        return None, "incomplete_horizon"
    if not future or any(o["below_500"] is None for o in future):
        return None, "unknown_future"
    times = [t] + [o["time"] for o in future] + [t + HORIZON]
    if max(b - a for a, b in zip(times, times[1:])) > MAX_GAP:
        return None, "coverage_gap"
    return 0, "no_observed_event"


def build_rows(observations, start, end):
    times = [o["time"] for o in observations]
    # Fixed half-hour UTC grid independent of SPECI occurrence.
    t = start.replace(minute=(start.minute // 30) * 30, second=0, microsecond=0)
    if t < start:
        t += STEP
    features, labels = [], []
    while t < end:
        i = bisect_right(times, t)
        current = observations[i - 1] if i else None
        future = observations[i:bisect_right(times, t + HORIZON)]
        y, reason = target(current, future, t, end)
        labels.append(dict(time=iso(t), target_end=iso(t + HORIZON),
                           below_500_within_3h=y, label_status=reason))
        record = dict(time=iso(t), observation_time=None, observation_age_minutes=None,
                      hour_utc=t.hour + t.minute / 60, month=t.month)
        usable = current is not None and t - current["time"] <= MAX_AGE
        fields = list(parse(""))
        record.update({key: current[key] if usable else None for key in fields})
        record["ceiling_change_1h_ft"] = None
        record["spread_change_1h_c"] = None
        if usable:
            record.update(observation_time=iso(current["time"]),
                          observation_age_minutes=(t-current["time"]).total_seconds()/60)
            j = bisect_right(times, t - timedelta(hours=1))
            lagged = observations[j - 1] if j else None
            if lagged and t - timedelta(hours=1) - lagged["time"] <= MAX_AGE:
                for source, dest in [("ceiling_ft", "ceiling_change_1h_ft"),
                                     ("spread_c", "spread_change_1h_c")]:
                    if current[source] is not None and lagged[source] is not None:
                        record[dest] = current[source] - lagged[source]
        features.append(record)
        t += STEP
    return features, labels


def write_csv(path, rows):
    if not rows:
        raise ValueError("No output rows")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare(source, output, report):
    payload = source.read_bytes()
    manifest = json.loads(source.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(payload).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError("Source checksum differs from download manifest")
    rows = read_csv(payload.decode("utf-8-sig"))
    start, end = timestamp(manifest["start"]), timestamp(manifest["end_exclusive"])
    if not rows or any(not start <= timestamp(r["valid"]) < end for r in rows):
        raise ValueError("Empty or out-of-range source")
    observations, counts = load_observations(rows)
    features, labels = build_rows(observations, start, end)
    write_csv(output / "features.csv", features)
    write_csv(output / "labels.csv", labels)
    gaps = [(b["time"]-a["time"]).total_seconds()/60
            for a, b in zip(observations, observations[1:])]
    monthly = defaultdict(Counter)
    for obs in observations:
        month = obs["time"].strftime("%Y-%m")
        monthly[month]["observations"] += 1
        monthly[month]["below_500_observations"] += obs["below_500"] is True
        monthly[month]["unknown_ceiling_observations"] += obs["below_500"] is None
    for row in labels:
        monthly[row["time"][:7]]["label_" + row["label_status"]] += 1
    low_runs = 0
    previous = None
    for obs in observations:
        if obs["below_500"] is True and (previous is None or previous["below_500"] is not True
                                        or obs["time"] - previous["time"] > MAX_GAP):
            low_runs += 1
        previous = obs
    audit = dict(source=manifest, input_sha256=digest, counts=dict(counts),
                 first_observation=iso(observations[0]["time"]),
                 last_observation=iso(observations[-1]["time"]),
                 gap_minutes=dict(median=median(gaps) if gaps else None,
                                  maximum=max(gaps) if gaps else None,
                                  over_35=sum(g > 35 for g in gaps)),
                 observation_minute_counts=dict(Counter(o["time"].minute for o in observations)),
                 ceiling_states=dict(Counter(o["ceiling_state"] for o in observations)),
                 below_500_observations=sum(o["below_500"] is True for o in observations),
                 contiguous_low_runs=low_runs,
                 explicit_speci_prefix_rows=sum("SPECI" in r["metar"].split()[:2] for r in rows),
                 label_counts=dict(Counter(r["label_status"] for r in labels)),
                 feature_missing_counts={k: sum(r[k] is None for r in features)
                                         for k in features[0]},
                 monthly=dict(monthly),
                 protocol=dict(version=1, horizon_minutes=180, threshold_ft_exclusive=500,
                               grid_minutes=30, max_gap_minutes=35, max_age_minutes=35,
                               receipt_times_available=False),
                 limitations=["Observation-time research dataset; receipt times unavailable.",
                              "Corrections may have arrived later than observation time.",
                              "Events between reports are not observable.",
                              "Request includes specials, but their archive completeness is unverified.",
                              "No model has been trained or evaluated."])
    write_json(report, audit)
    print(json.dumps({"counts": audit["counts"], "gap_minutes": audit["gap_minutes"],
                      "label_counts": audit["label_counts"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    download = subs.add_parser("fetch")
    download.add_argument("--start", type=timestamp, required=True)
    download.add_argument("--end", type=timestamp, required=True)
    download.add_argument("--output", type=Path, required=True)
    build = subs.add_parser("prepare")
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        fetch(args.start, args.end, args.output)
    else:
        prepare(args.input, args.output, args.report)


if __name__ == "__main__":
    main()
