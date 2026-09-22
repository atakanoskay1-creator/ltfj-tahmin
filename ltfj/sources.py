"""Public research archives, cached with URL and checksum provenance."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .pipeline import iso, write_json


def download(url, path):
    metadata = path.with_suffix(path.suffix + ".source.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if metadata.exists():
            old = json.loads(metadata.read_text(encoding="utf-8"))
            if old["url"] != url or old["sha256"] != digest:
                raise ValueError(f"Cached source mismatch: {path}")
        else:
            write_json(metadata, dict(url=url, sha256=digest, bytes=len(payload),
                retrieved_at=iso(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)),
                note="Provenance registered for previously downloaded file."))
        print(f"Cached {path}", flush=True)
        return
    request = Request(url, headers={"User-Agent": "ltfj-tahmin/0.2 public archive research"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=180) as response:
                payload = response.read()
            if payload.lstrip().startswith((b"<!DOCTYPE", b"<html")):
                raise ValueError("Expected data, received HTML")
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(payload)
    temporary.replace(path)
    write_json(metadata, dict(url=url, sha256=hashlib.sha256(payload).hexdigest(),
                             bytes=len(payload), retrieved_at=iso(datetime.now(timezone.utc))))
    print(f"Downloaded {path}: {len(payload)} bytes", flush=True)


def verified(path):
    payload = path.read_bytes()
    metadata = json.loads(path.with_suffix(path.suffix + ".source.json").read_text(encoding="utf-8"))
    if hashlib.sha256(payload).hexdigest() != metadata["sha256"]:
        raise ValueError(f"Checksum mismatch: {path}")
    return payload.decode("utf-8-sig"), metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", default="2026-09-21")
    args = parser.parse_args()
    for year in range(2021, 2027):
        url = ("https://www.ncei.noaa.gov/oa/global-historical-climatology-network/"
               f"hourly/access/by-year/{year}/psv/GHCNh_TUI0000LTFJ_{year}.psv")
        download(url, Path(f"data/raw/GHCNh_LTFJ_{year}.psv"))
    for stations, start, name in [("LTFJ", "2026-01-01", "LTFJ_2026"),
                                   ("LTBA,LTFM,LTBQ,LTBR", "2021-01-01", "neighbors_2021_2026")]:
        params = dict(station=stations, data="metar", sts=start+"T00:00:00Z",
                      ets=args.end+"T00:00:00Z", tz="Etc/UTC", format="onlycomma",
                      latlon="no", elev="no", missing="M", direct="no", report_type="3,4")
        url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?" + urlencode(params)
        download(url, Path(f"data/raw/{name}.csv"))
        time.sleep(1.1)


if __name__ == "__main__":
    main()
