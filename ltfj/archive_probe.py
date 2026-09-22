"""Small reproducible coverage probes, not a full model training dataset."""
import csv
import io
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qs
from urllib.error import HTTPError

from .pipeline import write_json
from .sources import download, verified

VARIABLES = ["Temperature_isobaric", "Relative_humidity_isobaric",
             "u-component_of_wind_isobaric", "v-component_of_wind_isobaric",
             "Geopotential_height_isobaric"]


def validate_sample(rows, cycle, lead, variables):
    expected = (datetime.strptime(cycle, "%Y%m%d%H").replace(tzinfo=timezone.utc)
                + timedelta(hours=lead)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if len(rows) != 1 or rows[0].get("time") != expected:
        raise ValueError("Forecast valid time or row count mismatch")
    for var in variables:
        keys = [k for k in rows[0] if k.startswith(var + "[")]
        if len(keys) != 1 or not math.isfinite(float(rows[0][keys[0]])):
            raise ValueError(f"Missing or non-finite variable: {var}")


def gfs_url(cycle, lead=6, pressure_pa=92500):
    if lead <= 0:
        raise ValueError("Probe requires a forecast, not a zero-hour analysis")
    date = cycle[:8]
    base = ("https://tds.gdex.ucar.edu/thredds/ncss/grid/files/g/d084001/"
            f"{cycle[:4]}/{date}/gfs.0p25.{cycle}.f{lead:03d}.grib2")
    return base + "?" + urlencode(dict(var=",".join(VARIABLES), latitude=40.9,
        longitude=29.3, vertCoord=pressure_pa, time="all", accept="csv"))


def main():
    report = dict(note="Point samples only; does not establish continuous coverage or historical publication latency.", probes=[])
    for cycle in ["2021010100", "2023010100", "2024010100"]:
        path = Path(f"data/raw/archive-probes/gfs_{cycle}_f006_925.csv")
        url = gfs_url(cycle)
        try:
            download(url, path)
            content, metadata = verified(path)
            rows = list(csv.DictReader(io.StringIO(content)))
            validate_sample(rows, cycle, 6, VARIABLES)
            report["probes"].append(dict(cycle=cycle, status="sample_downloaded",
                rows=rows, source=metadata))
        except Exception as exc:
            detail = exc.read(2000).decode("utf-8", errors="replace") if isinstance(exc, HTTPError) else ""
            report["probes"].append(dict(cycle=cycle, status="failed", url=url, error=str(exc), detail=detail))
            # Some old files expose incompatible coordinate axes in a combined CSV.
            # Keep the failed request and test each variable separately, without inventing values.
            if "illegal member name" in detail:
                parts = urlsplit(url)
                for variable in VARIABLES:
                    query = parse_qs(parts.query); query["var"] = [variable]
                    single_url = urlunsplit(parts._replace(query=urlencode(query, doseq=True)))
                    single_path = Path(f"data/raw/archive-probes/gfs_{cycle}_{variable}.csv")
                    download(single_url, single_path)
                    content, metadata = verified(single_path)
                    rows = list(csv.DictReader(io.StringIO(content)))
                    validate_sample(rows, cycle, 6, [variable])
                    report["probes"].append(dict(cycle=cycle, variable=variable,
                        status="single_variable_sample_downloaded", rows=rows, source=metadata))
        write_json(Path("reports/archive-probes.json"), report)
    for filename, station, start, end in [
        ("LTFJ_2024_01_probe.csv", "LTFJ", "2024-01-01", "2024-02-01"),
        ("LTFJ_2021_2026_probe.csv", "LTFJ", "2021-01-01", "2026-09-21"),
        ("DSM_control.csv", "DSM", "2024-01-01", "2024-01-02")]:
        url = (f"https://mesonet.agron.iastate.edu/cgi-bin/request/taf.py?station={station}"
               f"&sts={start}T00:00Z&ets={end}T00:00Z&fmt=csv&tz=UTC")
        path = Path("data/raw/taf")/filename
        download(url, path)
        content, metadata = verified(path)
        report["probes"].append(dict(source=metadata, file=filename,
            status="taf_query_completed", row_count=len(list(csv.DictReader(io.StringIO(content))))))
    write_json(Path("reports/archive-probes.json"), report)
    print(report)


if __name__ == "__main__":
    main()
