"""Create and append a live, pre-outcome LTFJ prediction from official sources."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import joblib
import numpy as np

from .gfs_coverage import forecast_bracket
from .gfs_features import at_origin
from .model import adjusted, matrix
from .pipeline import build_rows, iso, timestamp
from .research_data import NEIGHBORS, decoded, engineer, finish
from .sources import download

UTC = timezone.utc
STATIONS = ("LTFJ",) + NEIGHBORS
GFS_NAMES = {"t": "Temperature_isobaric", "r": "Relative_humidity_isobaric",
             "u": "u-component_of_wind_isobaric", "v": "v-component_of_wind_isobaric",
             "gh": "Geopotential_height_isobaric"}


def prediction_origin(now):
    now = now.astimezone(UTC)
    floor = now.replace(minute=30 if now.minute >= 30 else 0, second=0, microsecond=0)
    upcoming = floor + timedelta(minutes=30)
    return upcoming if upcoming - now <= timedelta(minutes=10) else floor


def fetch_metars(hours=5):
    query = urlencode({"ids": ",".join(STATIONS), "format": "json", "hours": hours})
    url = "https://aviationweather.gov/api/data/metar?" + query
    request = Request(url, headers={"User-Agent": "ltfj-tahmin/0.7 research"})
    with urlopen(request, timeout=30) as response:
        payload = response.read()
    rows = json.loads(payload)
    if not rows:
        raise ValueError("AWC returned no METAR observations")
    groups = {station: defaultdict(list) for station in STATIONS}
    for row in rows:
        station = row.get("icaoId")
        if station not in groups or not row.get("rawOb") or row.get("obsTime") is None:
            continue
        moment = datetime.fromtimestamp(float(row["obsTime"]), UTC)
        groups[station][moment].append(("AWC", decoded(row["rawOb"], moment, station)))
    observations = {}
    for station in STATIONS:
        observations[station], _ = finish(groups[station])
        if not observations[station]:
            raise ValueError(f"AWC returned no usable observations for {station}")
    return observations, payload, url


def live_feature(observations, origin):
    local = observations["LTFJ"]
    features, _ = build_rows(local, origin, origin + timedelta(minutes=30), delay_minutes=10)
    neighbors = {station: observations[station] for station in NEIGHBORS}
    engineer(features, local, neighbors, delay=10)
    return features[0]


def nomads_url(cycle, lead):
    query = {"file": f"gfs.t{cycle:%H}z.pgrb2.0p25.f{lead:03d}",
             "lev_850_mb": "on", "lev_925_mb": "on", "var_HGT": "on",
             "var_RH": "on", "var_TMP": "on", "var_UGRD": "on", "var_VGRD": "on",
             "subregion": "", "leftlon": "29.25", "rightlon": "29.25",
             "toplat": "41", "bottomlat": "41",
             "dir": f"/gfs.{cycle:%Y%m%d}/{cycle:%H}/atmos"}
    return "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?" + urlencode(query)


def decode_grib(path, cycle, lead):
    from eccodes import (codes_get, codes_get_values, codes_grib_new_from_file, codes_release)
    values = {}
    with path.open("rb") as handle:
        while True:
            message = codes_grib_new_from_file(handle)
            if message is None:
                break
            try:
                short = codes_get(message, "shortName")
                level = int(codes_get(message, "level"))
                if (short not in GFS_NAMES or codes_get(message, "typeOfLevel") != "isobaricInhPa"
                        or level not in {850, 925}):
                    raise ValueError("Unexpected GFS field or level")
                if (int(codes_get(message, "dataDate")) != int(cycle.strftime("%Y%m%d"))
                        or int(codes_get(message, "dataTime")) != cycle.hour * 100
                        or int(codes_get(message, "step")) != lead):
                    raise ValueError("Wrong GFS cycle or forecast lead")
                lat = float(codes_get(message, "latitudeOfFirstGridPointInDegrees"))
                lon = float(codes_get(message, "longitudeOfFirstGridPointInDegrees"))
                data = codes_get_values(message)
                if data.size != 1 or not np.isclose(lat, 41) or not np.isclose(lon, 29.25):
                    raise ValueError("Wrong GFS grid point")
                value = float(data[0])
                if not math.isfinite(value) or (short == "r" and not 0 <= value <= 100):
                    raise ValueError("Invalid GFS value")
                key = f"{GFS_NAMES[short]}_{level}"
                if key in values:
                    raise ValueError("Duplicate GFS field")
                values[key] = value
            finally:
                codes_release(message)
    if len(values) != 10:
        raise ValueError(f"Expected 10 GFS values, found {len(values)}")
    return {"cycle": iso(cycle), "lead_hours": lead,
            "valid_time": iso(cycle + timedelta(hours=lead)), **values}


def fetch_gfs(origin):
    cutoff = origin - timedelta(hours=6)
    cycle = cutoff.replace(hour=cutoff.hour // 6 * 6, minute=0, second=0, microsecond=0)
    leads = sorted(set(sum((list(forecast_bracket(origin, cycle, horizon)) for horizon in [0, 3]), [])))
    records, provenance = {}, []
    for lead in leads:
        path = Path("data/raw/live/gfs") / f"{cycle:%Y%m%d%H}_f{lead:03d}.grib2"
        url = nomads_url(cycle, lead)
        download(url, path, timeout=60, attempts=3)
        row = decode_grib(path, cycle, lead)
        records[(row["cycle"], lead)] = row
        provenance.append({"url": url, "path": str(path),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    features = at_origin(origin, records, delay_hours=6)
    if features["gfs_status"] != "available_under_assumption":
        raise ValueError("Required live GFS forecast bracket is incomplete")
    return features, provenance


def predict(row, gfs, artifact):
    if row["below_500"] is True:
        return {"status": "already_below_threshold", "local_probability": None,
                "gfs_probability": None, "local_alarm": None, "gfs_alarm": None}
    if row["below_500"] is not False or row["observation_age_minutes"] is None or row["observation_age_minutes"] > 35:
        return {"status": "insufficient_current_observation", "local_probability": None,
                "gfs_probability": None, "local_alarm": None, "gfs_alarm": None}
    combined = dict(row, **gfs)
    result = {"status": "research_estimate"}
    for name, prefix in [("matched_local", "local"), ("matched_local_gfs", "gfs")]:
        meta = artifact["metadata"][name]
        raw = artifact["models"][name].predict_proba(matrix([combined], meta["columns"]))[0, 1]
        probability = float(adjusted([raw], meta["offset"])[0])
        result[prefix + "_probability"] = probability
        result[prefix + "_alarm"] = probability >= meta["threshold"]
    return result


def append_prediction(path, entry):
    path.parent.mkdir(parents=True, exist_ok=True)
    previous, saved_by_time = "0" * 64, {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            saved = json.loads(line)
            previous = saved["entry_hash"]
            saved_by_time[saved["prediction_time"]] = saved
    if entry["prediction_time"] in saved_by_time:
        return saved_by_time[entry["prediction_time"]], False
    entry["previous_hash"] = previous
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    entry["entry_hash"] = hashlib.sha256(canonical).hexdigest()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    return entry, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", type=timestamp, help="UTC half-hour origin; default chooses the current operational grid")
    parser.add_argument("--ledger", type=Path, default=Path("data/processed/prospective/predictions.jsonl"))
    parser.add_argument("--model", type=Path, default=Path("models/ceiling-risk-gfs.joblib"))
    args = parser.parse_args()
    retrieved = datetime.now(UTC)
    origin = args.at or prediction_origin(retrieved)
    if origin.minute not in {0, 30} or origin.second or origin.microsecond:
        raise ValueError("Prediction origin must be on a UTC half-hour")
    if abs((origin - retrieved).total_seconds()) > 20 * 60:
        raise ValueError("Live prediction origin must be within 20 minutes of retrieval time")
    observations, metar_payload, metar_url = fetch_metars()
    row = live_feature(observations, origin)
    gfs, gfs_provenance = fetch_gfs(origin)
    artifact = joblib.load(args.model)
    result = predict(row, gfs, artifact)
    entry = {"kind": "prediction", "prediction_time": iso(origin), "recorded_at": iso(retrieved),
             **result, "gfs_cycle": gfs["gfs_cycle"], "observation_time": row["observation_time"],
             "metar_url": metar_url, "metar_sha256": hashlib.sha256(metar_payload).hexdigest(),
             "gfs_sources": gfs_provenance,
             "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest()}
    saved, created = append_prediction(args.ledger, entry)
    print(json.dumps({"record_status": "created" if created else "already_recorded", **saved}, indent=2))


if __name__ == "__main__":
    main()
