"""
bench_json.py

Runs repeated serialize (dumps) + deserialize (loads) cycles on a given
payload file using Python's standard library `json`. Meant to be launched
UNDER EnergiBridge, not run standalone for measurement purposes (though it
works fine standalone too, e.g. for a quick timing sanity check).

Usage:
    python3 bench_json.py <payload_file> <iterations>

Example:
    python3 bench_json.py payloads/medium_flat.json 1000
"""

import json
import sys
import time


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 bench_json.py <payload_file> <iterations>")
        sys.exit(1)

    payload_path = sys.argv[1]
    iterations = int(sys.argv[2])

    with open(payload_path, "r") as f:
        data = json.load(f)  # load once; not part of the measured loop

    start = time.perf_counter()
    for _ in range(iterations):
        encoded = json.dumps(data)
        decoded = json.loads(encoded)
    elapsed = time.perf_counter() - start

    print(f"library=json payload={payload_path} iterations={iterations} "
          f"elapsed_s={elapsed:.4f}")


if __name__ == "__main__":
    main()