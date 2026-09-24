"""Reject successful HTTP responses that silently omit requested forecast fields."""
import json
from pathlib import Path
from scipy.io import netcdf_file
from .archive_probe import VARIABLES
from .pipeline import write_json


def missing_variables(names):
    return sorted(set(VARIABLES) - set(names))


def main():
    path = Path("data/raw/gfs-coverage/2021011500_profile.nc")
    with netcdf_file(path, mmap=False) as data:
        names = list(data.variables)
        missing = missing_variables(names)
    result = dict(status="rejected" if missing else "variables_present_not_fully_validated",
        requested=VARIABLES, returned=names, missing=missing,
        source=json.loads(path.with_suffix(".nc.source.json").read_text()),
        decision="Do not use combined profile transport until all fields, levels and times are validated.")
    write_json(Path("reports/gfs-profile-check.json"), result)
    print(result)


if __name__ == "__main__":
    main()
