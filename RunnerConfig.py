"""
RunnerConfig for "json vs orjson" (Green Lab 2026/2027).

Run from the root of the experiment-runner fork, ON THE SERVER:

    python3 experiment-runner/ examples/json-vs-orjson/RunnerConfig.py

Design implemented here (must match Sections 4 and 5 of the report):
  factors      library (json, orjson) x operation (dumps, loads) x payload (14)
  repetitions  30  ->  2 x 2 x 14 x 30 = 1,680 runs
  order        fully randomised (shuffle), seeded so the run table is reproducible
  warm-up      once, before the first run
  cool-down    between every two runs
  per run      a fresh Python process (bench.py) launched under EnergiBridge
"""

from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ProgressManager.Output.OutputProcedure import OutputProcedure as output
from Plugins.Profilers.EnergiBridge import EnergiBridge

from typing import Dict, Any, Optional
from pathlib import Path
from os.path import dirname, realpath
import json
import random
import shlex
import subprocess
import sys
import time

import numpy as np
import pandas as pd


# =============================== EXPERIMENT PARAMETERS ===============================
# TODO: confirm with the team (Section 4) -- change here, nothing else needs to change.
LIBRARIES   = ["json", "orjson"]
OPERATIONS  = ["dumps", "loads"]
PAYLOADS    = ["R1", "R2", "R3", "R4",                 # real-world  (Table 4)
               "S0", "S1", "S2", "S3", "S4",           # synthetic   (Table 5)
               "S5", "S6", "S7", "S8", "S9"]
REPETITIONS = 30
VOLUME_MB   = 1024        # TODO: calibrate in the pilot so the fastest run lasts >= 1-2 s
WARMUP_S    = 120         # TODO: warm-up duration (lecture 04-B uses 2 min)
COOLDOWN_S  = 30          # TODO: cool-down between runs (report currently says 30 s)
IDLE_S      = 60          # idle measurement used for baseline correction
SAMPLING_MS = 100         # EnergiBridge sampling interval
RUN_ORDER_SEED = 2026     # makes the shuffled run table reproducible
# =====================================================================================


class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))

    # ================================ USER SPECIFIC CONFIG ================================
    name:                       str             = "json_vs_orjson"
    results_output_path:        Path            = ROOT_DIR / "experiments"
    operation_type:             OperationType   = OperationType.AUTO
    time_between_runs_in_ms:    int             = COOLDOWN_S * 1000

    PAYLOAD_DIR = ROOT_DIR / "payloads"
    BENCH       = ROOT_DIR / "bench.py"

    def __init__(self):
        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN       , self.before_run       ),
            (RunnerEvents.START_RUN        , self.start_run        ),
            (RunnerEvents.START_MEASUREMENT, self.start_measurement),
            (RunnerEvents.INTERACT         , self.interact         ),
            (RunnerEvents.STOP_MEASUREMENT , self.stop_measurement ),
            (RunnerEvents.STOP_RUN         , self.stop_run         ),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT , self.after_experiment )
        ])
        self.run_table_model = None
        self.profiler = None
        self.idle_power_w = 0.0
        output.console_log("json vs orjson config loaded")

    # ------------------------------------------------------------------ run table
    def create_run_table_model(self) -> RunTableModel:
        random.seed(RUN_ORDER_SEED)   # the shuffle below becomes reproducible
        self.run_table_model = RunTableModel(
            factors=[
                FactorModel("library",   LIBRARIES),
                FactorModel("operation", OPERATIONS),
                FactorModel("payload",   PAYLOADS),
            ],
            repetitions=REPETITIONS,
            shuffle=True,
            data_columns=[
                "energy_j",                    # package (+ DRAM if exposed), measurement window only
                "energy_pkg_j",
                "energy_dram_j",
                "energy_corrected_j",          # energy_j minus idle energy over the same duration
                "energy_eff_j_per_kb",         # energy_corrected_j / processed KB
                "execution_time_s",
                "cpu_util_pct",
                "peak_rss_bytes",
                "peak_rss_minus_baseline_bytes",
                "iterations",
                "payload_bytes",
            ],
        )
        return self.run_table_model

    # ------------------------------------------------------------ experiment setup
    def before_experiment(self) -> None:
        self._check_payloads()
        self._measure_idle_power()
        self._warm_up()

    def _check_payloads(self) -> None:
        """Every payload must exist and deserialise to equal objects with both libraries."""
        import orjson
        for pid in PAYLOADS:
            path = self.PAYLOAD_DIR / f"{pid}.json"
            if not path.exists():
                raise FileNotFoundError(f"missing payload {path}")
            raw = path.read_bytes()
            if json.loads(raw) != orjson.loads(raw):
                raise ValueError(f"{pid}: json and orjson disagree on deserialisation")
        output.console_log(f"All {len(PAYLOADS)} payloads present and equivalent")

    def _measure_idle_power(self) -> None:
        """Idle power of the machine, subtracted later (baseline correction)."""
        out = self.results_output_path / "idle_energibridge.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        profiler = EnergiBridge(target_program=f"sleep {IDLE_S}",
                                out_file=out, sample_frequency=SAMPLING_MS)
        profiler.start()
        profiler.stop(wait=True)
        df = pd.read_csv(out)
        energy = _energy_columns(df)
        duration_s = (df["Time"].iloc[-1] - df["Time"].iloc[0]) / 1000
        total = sum(df[c].iloc[-1] - df[c].iloc[0] for c in energy.values() if c)
        self.idle_power_w = total / duration_s
        output.console_log(f"Idle power: {self.idle_power_w:.2f} W")

    def _warm_up(self) -> None:
        """CPU-bound busy work so the machine reaches a stable temperature."""
        output.console_log(f"Warm-up for {WARMUP_S} s")
        busy = ("import time\n"
                f"end = time.time() + {WARMUP_S}\n"
                "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)\n"
                "while time.time() < end: fib(25)\n")
        subprocess.run([sys.executable, "-c", busy], check=True)
        time.sleep(COOLDOWN_S)

    # ---------------------------------------------------------------------- runs
    def before_run(self) -> None:
        pass

    def start_run(self, context: RunnerContext) -> None:
        pass

    def start_measurement(self, context: RunnerContext) -> None:
        v = context.execute_run
        cmd = " ".join(shlex.quote(str(x)) for x in [
            sys.executable, self.BENCH,
            "--library",   v["library"],
            "--operation", v["operation"],
            "--payload",   self.PAYLOAD_DIR / f"{v['payload']}.json",
            "--volume-mb", VOLUME_MB,
            "--out",       context.run_dir / "window.json",
        ])
        self.profiler = EnergiBridge(target_program=cmd,
                                     out_file=context.run_dir / "energibridge.csv",
                                     sample_frequency=SAMPLING_MS)
        self.profiler.start()

    def interact(self, context: RunnerContext) -> None:
        pass   # bench.py runs to completion on its own

    def stop_measurement(self, context: RunnerContext) -> None:
        self.profiler.stop(wait=True)

    def stop_run(self, context: RunnerContext) -> None:
        pass

    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, Any]]:
        window = json.loads((context.run_dir / "window.json").read_text())
        df = pd.read_csv(context.run_dir / "energibridge.csv")

        # Energy counters are cumulative: interpolate them at the start and end of the
        # measurement window, so start-up and payload loading are not counted.
        t = df["Time"].to_numpy(dtype=float)
        start, end = window["window_start_ms"], window["window_end_ms"]
        if not (t[0] <= start and end <= t[-1]):
            output.console_log("[WARNING] window outside EnergiBridge samples, using whole run")
            start, end = t[0], t[-1]

        cols = _energy_columns(df)
        def delta(col):
            if col is None:
                return 0.0
            y = df[col].to_numpy(dtype=float)
            return float(np.interp(end, t, y) - np.interp(start, t, y))

        e_pkg, e_dram = delta(cols["pkg"]), delta(cols["dram"])
        energy = e_pkg + e_dram
        corrected = energy - self.idle_power_w * window["execution_time_s"]

        return {
            "energy_j":                      round(energy, 4),
            "energy_pkg_j":                  round(e_pkg, 4),
            "energy_dram_j":                 round(e_dram, 4),
            "energy_corrected_j":            round(corrected, 4),
            "energy_eff_j_per_kb":           corrected / window["processed_kb"],
            "execution_time_s":              round(window["execution_time_s"], 4),
            "cpu_util_pct":                  round(window["cpu_util_pct"], 2),
            "peak_rss_bytes":                window["peak_rss_bytes"],
            "peak_rss_minus_baseline_bytes": window["peak_rss_minus_baseline_bytes"],
            "iterations":                    window["iterations"],
            "payload_bytes":                 window["payload_bytes"],
        }

    def after_experiment(self) -> None:
        output.console_log("Experiment finished")

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None


def _energy_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """EnergiBridge column names differ across machines: find package and DRAM counters."""
    pkg = next((c for c in df.columns if "PACKAGE_ENERGY" in c), None)
    dram = next((c for c in df.columns if "DRAM_ENERGY" in c), None)
    if pkg is None:
        raise KeyError(f"no PACKAGE_ENERGY column in EnergiBridge output: {list(df.columns)}")
    return {"pkg": pkg, "dram": dram}
