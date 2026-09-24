"""Build an outcome-independent acquisition manifest without downloading full grids."""
import csv
from datetime import timedelta
from pathlib import Path

from .gfs_coverage import select_cycle, forecast_bracket
from .pipeline import iso, timestamp, write_csv, write_json


def main():
    folder = Path("data/processed/research")
    requests = set()
    origins = 0
    with (folder/"features.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            t = timestamp(row["time"])
            available = t - timedelta(hours=6)
            cycle = available.replace(hour=(available.hour//6)*6, minute=0, second=0, microsecond=0)
            if select_cycle(t, [cycle]) != cycle:
                raise ValueError("Planned cycle violates availability rule")
            # Current forecast context and the next three hours; hourly target sampling
            # brackets the 3-hourly model fields without changing the binary METAR label.
            for horizon in [0.5, 1, 2, 3]:
                for lead in forecast_bracket(t, cycle, horizon):
                    requests.add((iso(cycle), lead))
            origins += 1
    records = [dict(cycle=cycle, lead_hours=lead, levels_hpa="925,850",
                    variables="temperature,relative_humidity,u_wind,v_wind,geopotential_height")
               for cycle, lead in sorted(requests)]
    write_csv(folder/"gfs-acquisition-plan.csv", records)
    report = dict(status="planned_only_not_downloaded", origins=origins,
        unique_cycle_lead_files=len(records), first=records[0], last=records[-1],
        assumed_publication_delay_hours=6, sensitivity_delay_hours=[9,12],
        naive_single_variable_requests=len(records)*2*5,
        decision="Use a batched subset transport before full acquisition; do not issue the naive request count.",
        guardrails=["No labels consulted when selecting acquisition times.",
            "Run initialization and archive modification are not historical publication timestamps.",
            "Six hours is an unverified latency assumption, not a guarantee.",
            "Retain missing data and compare models on matched origins with coverage reported.",
            "Do not interpolate observations into forecast fields."])
    write_json(Path("reports/gfs-acquisition-plan.json"), report)
    print(report)


if __name__ == "__main__":
    main()
