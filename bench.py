"""
bench.py -- one experimental run (json vs orjson).

Launched by Experiment Runner *under EnergiBridge* for every row of the run table:

    python3 bench.py --library orjson --operation loads \
                     --payload payloads/S0.json --volume-mb 1024 \
                     --out run_dir/window.json

What it does:
  1. Setup (NOT measured): reads the payload file and prepares the input
     for the chosen operation (a Python object for dumps, UTF-8 bytes for loads).
  2. Measurement window: repeats the operation until VOLUME_MB of JSON has been
     processed (fixed amount of work, not fixed duration -- see Section 4.2).
  3. Writes the window's start/end timestamps, CPU utilisation and memory
     to --out, so RunnerConfig can keep only the EnergiBridge samples that
     fall inside the window (process start-up and payload loading excluded).

The same file is used for both libraries: only the two functions picked in
`get_ops()` differ, so library implementation is the only varying factor.
"""

import argparse
import json
import math
import os
import threading
import time

import psutil


# ------------------------------------------------------------------ libraries
def json_dumps(obj):
    # Same output as orjson.dumps(obj): compact, non-ASCII kept, UTF-8 bytes.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def json_loads(data):
    return json.loads(data)


def get_ops(library):
    if library == "json":
        # Make sure we compare against the C-accelerated json developers actually use.
        import json.decoder
        import json.encoder
        assert json.decoder.c_scanstring is not None, "json C accelerator (scanner) not active"
        assert json.encoder.c_make_encoder is not None, "json C accelerator (encoder) not active"
        return json_dumps, json_loads
    if library == "orjson":
        import orjson
        return orjson.dumps, orjson.loads
    raise ValueError(f"unknown library: {library}")


# ------------------------------------------------------------ memory sampler
class RssSampler(threading.Thread):
    """Samples the resident set size of this process every `interval` s."""

    def __init__(self, interval=0.01):
        super().__init__(daemon=True)
        self.proc = psutil.Process(os.getpid())
        self.interval = interval
        self.peak = 0
        self._stop_evt = threading.Event()

    def run(self):
        while not self._stop_evt.is_set():
            self.peak = max(self.peak, self.proc.memory_info().rss)
            time.sleep(self.interval)

    def stop(self):
        self._stop_evt.set()
        self.join()
        self.peak = max(self.peak, self.proc.memory_info().rss)


# ---------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--library", required=True, choices=["json", "orjson"])
    p.add_argument("--operation", required=True, choices=["dumps", "loads"])
    p.add_argument("--payload", required=True)
    p.add_argument("--volume-mb", type=float, required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    dumps, loads = get_ops(args.library)

    # ---- setup (outside the measurement window)
    with open(args.payload, "rb") as f:
        raw = f.read()
    obj = json.loads(raw)                 # the same Python object for both libraries
    payload_bytes = json_dumps(obj)       # canonical compact form
    size = len(payload_bytes)             # bytes processed per operation

    if args.operation == "dumps":
        op, arg = dumps, obj
    else:
        op, arg = loads, payload_bytes

    iterations = max(1, math.ceil(args.volume_mb * 1024 * 1024 / size))

    proc = psutil.Process(os.getpid())
    rss_before = proc.memory_info().rss
    sampler = RssSampler()
    sampler.start()

    # ---- measurement window
    cpu_before = proc.cpu_times()
    t_epoch_start = time.time()
    t0 = time.perf_counter()

    for _ in range(iterations):
        op(arg)

    t1 = time.perf_counter()
    t_epoch_end = time.time()
    cpu_after = proc.cpu_times()
    # ---- end of window

    sampler.stop()

    wall = t1 - t0
    cpu_s = (cpu_after.user - cpu_before.user) + (cpu_after.system - cpu_before.system)

    result = {
        "library": args.library,
        "operation": args.operation,
        "payload": os.path.basename(args.payload),
        "payload_bytes": size,
        "iterations": iterations,
        "processed_kb": iterations * size / 1024,
        "window_start_ms": t_epoch_start * 1000,
        "window_end_ms": t_epoch_end * 1000,
        "execution_time_s": wall,
        # CPU utilisation of this process over the window (100% = one core busy)
        "cpu_util_pct": 100 * cpu_s / wall if wall > 0 else 0.0,
        "peak_rss_bytes": sampler.peak,
        "peak_rss_minus_baseline_bytes": sampler.peak - rss_before,
    }
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
