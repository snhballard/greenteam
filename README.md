# json vs orjson — experiment execution

Experiment Runner configuration for our Green Lab study. It lives in our fork of
[experiment-runner](https://github.com/S2-group/experiment-runner) under
`examples/json-vs-orjson/`.

| File | What it is |
|---|---|
| `RunnerConfig.py` | The experiment: factors, repetitions, warm-up, cool-down, how each run is measured. All parameters are at the top of the file. |
| `bench.py` | One run: loads a payload, repeats `dumps` or `loads` until `VOLUME_MB` is processed, records its measurement window. |
| `generate_run_table.py` | Writes `run_table.csv` without running the experiment (Assignment 2 deliverable). |
| `run_table.csv` | 2 libraries × 2 operations × 14 payloads × 30 repetitions = 1,680 runs, shuffled (seed 2026). |
| `payloads/` | `R1.json` … `R4.json`, `S0.json` … `S9.json` (to be added). |

## Requirements (on the server)

- Linux on an Intel/AMD CPU (EnergiBridge reads RAPL), `sudo` rights
- Python **3.12+** (experiment-runner uses 3.12 f-string syntax)
- [EnergiBridge](https://github.com/tdurieux/EnergiBridge) on the `PATH`
- In a virtualenv: `pip install -r requirements.txt orjson==3.12.0 numpy`

## Generate the run table

```bash
python3 examples/json-vs-orjson/generate_run_table.py
```

## Run the experiment

```bash
tmux new -s greenlab          # keeps running if the SSH connection drops
source .venv/bin/activate
python3 experiment-runner/ examples/json-vs-orjson/RunnerConfig.py
```

Results go to `examples/json-vs-orjson/experiments/json_vs_orjson/`:
`run_table.csv` with all metrics filled in, plus one folder per run with the raw
EnergiBridge CSV (`energibridge.csv`) and the measurement window (`window.json`).
If the experiment is interrupted, the same command resumes from the first unfinished run.

## How a run is measured

1. `before_experiment` (once): check payloads (both libraries must deserialise them to
   equal objects) → measure idle power for 60 s → warm-up for 120 s.
2. Each run: EnergiBridge starts `bench.py` in a fresh Python process. `bench.py` loads
   the payload *before* the measurement window, then runs the operation and saves the
   window's start/end timestamps, CPU utilisation and peak RSS.
3. `populate_run_data`: the cumulative energy counters are interpolated at the window's
   start and end, so process start-up and payload loading are excluded. Idle energy over
   the same duration is subtracted (`energy_corrected_j`).
4. Cool-down of 30 s before the next run.
