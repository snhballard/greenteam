"""
generate_run_table.py -- writes the run table (deliverable of Assignment 2)
WITHOUT running the experiment.

It builds the table from RunnerConfig.py itself, so the two can never disagree.
Because the shuffle is seeded (RUN_ORDER_SEED), the order written here is the
same order Experiment Runner will follow when the experiment is launched.

Run from the root of the experiment-runner fork:
    python3 examples/json-vs-orjson/generate_run_table.py
"""

import csv
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ER_ROOT = HERE.parent.parent / "experiment-runner"   # <fork>/experiment-runner
sys.path.insert(0, str(ER_ROOT))

spec = importlib.util.spec_from_file_location("RunnerConfig", HERE / "RunnerConfig.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

config = module.RunnerConfig()
rows = config.create_run_table_model().generate_experiment_run_table()

out = HERE / "run_table.csv"
with open(out, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    for row in rows:
        row["__done"] = "TODO"
        writer.writerow(row)

print(f"{len(rows)} runs written to {out}")
