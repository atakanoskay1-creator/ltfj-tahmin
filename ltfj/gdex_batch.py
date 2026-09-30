"""Prepare and operate authenticated NCAR GDEX server-side GFS subset requests."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .pipeline import write_json
from .sources import download

API = "https://gdex.ucar.edu/api/"
ROOT = Path("data/raw/gdex-batch")
PARAMETERS = "TMP/R H/U GRD/V GRD/HGT"
PRODUCTS = "6-hour Forecast/9-hour Forecast/12-hour Forecast/15-hour Forecast"


def control(start, end):
    """GDEX dates are initialization times; end is inclusive."""
    for value in [start, end]:
        datetime.strptime(value, "%Y%m%d%H%M")
    if start > end:
        raise ValueError("Start is after end")
    return dict(dataset="d084001", date=f"{start}/to/{end}", datetype="init",
        param=PARAMETERS, level="ISBL:925/850", oformat="netCDF",
        nlat="41", slat="41", wlon="29.25", elon="29.25",
        product=PRODUCTS, targetdir="/glade/scratch")


def controls():
    return {str(year): control(f"{year}01010000",
        "202609201200" if year == 2026 else f"{year}12311800") for year in range(2021, 2027)} | {
        "2020_tail": control("202012311800", "202012311800")}


def api(method, endpoint, token, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    url = API + endpoint.lstrip("/") + "?" + urlencode(dict(token=token))
    request = Request(url, data=body, method=method,
        headers={"Content-Type": "application/json", "User-Agent": "ltfj-tahmin/0.4 research"})
    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read())
    except HTTPError as error:
        # The URL carries the token, so only the status code and GDEX messages are reported.
        try:
            messages = json.loads(error.read()).get("messages")
        except ValueError:
            messages = None
        raise RuntimeError(f"GDEX API HTTP {error.code} on {endpoint}: {messages}") from None
    return unwrap(result)


def unwrap(result):
    """GDEX returns {"status", "messages", "result"}; errors are reported in messages."""
    if result.get("status") not in {"ok", None} or result.get("error_messages"):
        raise RuntimeError(f"GDEX API error: {result.get('messages') or result.get('error_messages')}")
    return result.get("result", result.get("data", result))


def token():
    value = os.environ.get("GDEX_TOKEN", "").strip()
    if not value:
        raise RuntimeError("GDEX_TOKEN is missing; create a free GDEX account and set it only in the environment")
    return value


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    plan = controls()
    for name, item in plan.items():
        write_json(ROOT/f"control-{name}.json", item)
    report = dict(status="prepared_not_submitted", requests=len(plan), controls=plan,
        estimated_original_file_requests=33424,
        source="NCAR GDEX d084001 server-side subset API",
        authentication="GDEX_TOKEN environment variable; never written to files",
        note="Server-side output still requires validation before model training.")
    write_json(Path("reports/gdex-batch-plan.json"), report)
    return report


def submit():
    prepare(); secret = token()
    state_path = ROOT/"requests.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    for name, item in controls().items():
        if name in state:
            continue
        response = api("POST", "submit/", secret, item)
        request_id = response.get("request_id") if isinstance(response, dict) else None
        if not request_id:
            raise RuntimeError("GDEX did not return request_id")
        state[name] = dict(request_id=str(request_id), submitted_at=datetime.now(timezone.utc).isoformat())
        write_json(state_path, state)
    return state


def status():
    secret = token(); state_path = ROOT/"requests.json"
    state = json.loads(state_path.read_text())
    for item in state.values():
        item["status_response"] = api("GET", f"status/{item['request_id']}", secret)
    write_json(state_path, state)
    return state


def fetch():
    secret = token(); state_path = ROOT/"requests.json"
    state = json.loads(state_path.read_text())
    for name, item in state.items():
        current = api("GET", f"status/{item['request_id']}", secret)
        item["status_response"] = current
        if not isinstance(current, dict) or current.get("status") != "Completed":
            print(f"{name}: not ready ({current.get('status') if isinstance(current, dict) else current})", flush=True)
            write_json(state_path, state)
            continue
        listing = api("GET", f"get_req_files/{item['request_id']}", secret)
        files = listing.get("web_files", []) if isinstance(listing, dict) else []
        item["files"] = []
        for entry in files:
            url = entry["web_path"]
            filename = Path(urlsplit(url).path).name
            if not filename:
                raise ValueError("Unsafe empty GDEX filename")
            path = ROOT/name/filename
            download(url, path, timeout=180, attempts=3)
            if entry.get("size") is not None and path.stat().st_size != int(entry["size"]):
                raise ValueError(f"Size mismatch for {path}: expected {entry['size']} bytes")
            item["files"].append(dict(path=str(path), expected_bytes=entry.get("size")))
        write_json(state_path, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "submit", "status", "fetch"])
    args = parser.parse_args()
    result = globals()[args.action]()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
