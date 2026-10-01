"""Repair the small set of files omitted from a GDEX batch archive."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

from .gfs_download import decode, grid_url
from .pipeline import timestamp, write_json
from .sources import download


def acquire(item):
    cycle = timestamp(item["cycle"]).strftime("%Y%m%d%H")
    lead = int(item["lead_hours"])
    root = Path("data/raw/gfs-grid")
    path = root / f"{cycle}_f{lead:03d}.nc"
    sidecar = path.with_suffix(".validated.json")
    if sidecar.exists() and path.exists():
        saved = json.loads(sidecar.read_text())
        if saved["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest():
            return {"cycle": cycle, "lead_hours": lead, "status": "cached"}
    download(grid_url(cycle, lead), path, timeout=60, attempts=3)
    values = decode(path, cycle, lead)
    write_json(sidecar, {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "values": values})
    return {"cycle": cycle, "lead_hours": lead, "status": "downloaded"}


def main():
    report = json.loads(Path("reports/gdex-ingest.json").read_text())
    missing = report.get("missing", [])
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="gfs-repair") as pool:
        futures = {pool.submit(acquire, item): item for item in missing}
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                print(result["status"], result["cycle"], result["lead_hours"], flush=True)
            except Exception as exc:
                failures.append({**futures[future], "error": str(exc)})
    output = {"requested": len(missing), "repaired": len(results), "failures": failures}
    write_json(Path("reports/gfs-repair.json"), output)
    print(json.dumps(output, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
