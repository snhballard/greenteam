"""
generate_payloads.py

Generates a small set of JSON payload files with varying:
- size (number of records / overall byte size)
- nesting depth
- data type composition (str, int, float, bool, null, list, nested dict)

These are the "subjects" your json vs orjson benchmarks will run against.
Run once, then reuse the same files across all json/orjson trials so the
payload itself is held constant (only library implementation varies).

Usage:
    python3 generate_payloads.py
"""

import json
import os
import random
import string

random.seed(42)  # reproducibility across regenerations

OUT_DIR = "payloads"


def random_string(n=8):
    return "".join(random.choices(string.ascii_letters, k=n))


def flat_record():
    """A flat dict with mixed primitive types (depth = 1)."""
    return {
        "id": random.randint(1, 1_000_000),
        "name": random_string(10),
        "score": round(random.uniform(0, 100), 3),
        "active": random.choice([True, False]),
        "tag": random.choice(["a", "b", "c", None]),
    }


def nested_record(depth):
    """A dict that nests `depth` levels deep, mixing types at each level."""
    if depth <= 0:
        return {
            "id": random.randint(1, 1_000_000),
            "value": round(random.uniform(0, 1), 4),
            "label": random_string(6),
        }
    return {
        "id": random.randint(1, 1_000_000),
        "name": random_string(8),
        "metrics": [round(random.uniform(0, 1), 3) for _ in range(3)],
        "child": nested_record(depth - 1),
    }


def build_flat_payload(n_records):
    """List of n flat records -> varies SIZE while holding depth constant."""
    return [flat_record() for _ in range(n_records)]


def build_nested_payload(n_records, depth):
    """List of n records each nested to `depth` -> varies DEPTH."""
    return [nested_record(depth) for _ in range(n_records)]


def save(payload, filename):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w") as f:
        json.dump(payload, f)
    size_kb = os.path.getsize(path) / 1024
    print(f"{filename:25s} {size_kb:10.1f} KB")


if __name__ == "__main__":
    print(f"{'file':25s} {'size':>10s}")

    # SIZE variation (depth held constant at flat, depth=1)
    save(build_flat_payload(10), "small_flat.json")        # ~small
    save(build_flat_payload(1_000), "medium_flat.json")    # ~medium
    save(build_flat_payload(50_000), "large_flat.json")    # ~large

    # DEPTH variation (record count held constant at 500)
    save(build_nested_payload(500, depth=1), "shallow_nested.json")
    save(build_nested_payload(500, depth=5), "medium_nested.json")
    save(build_nested_payload(500, depth=15), "deep_nested.json")

    print("\nDone. Payload files are in ./payloads/")