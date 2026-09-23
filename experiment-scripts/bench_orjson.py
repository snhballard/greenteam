"""
bench_orjson.py

Mirror of bench_json.py but using orjson instead of the standard library.
Kept structurally identical (same loop, same I/O, same argument handling)
so that library implementation is the ONLY thing that differs between
the two scripts -- this matters for construct validity later.

Note: orjson.dumps returns bytes, not str, and orjson.loads accepts both
bytes and str. This is a real API difference from json, not a bug.

Install first:
    pip install orjson --break-system-packages

Usage:
    python3 bench_orjson.py <payload_file> <iterations>

Example:
    python3 bench_orjson.py payloads/medium_flat.json 1000
"""

import sys
import time

import orjson


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 bench_orjson.py <payload_file> <iterations>")
        sys.exit(1)

    payload_path = sys.argv[1]
    iterations = int(sys.argv[2])

    with open(payload_path, "rb") as f:
        data = orjson.loads(f.read())  # load once; not part of the measured loop

    start = time.perf_counter()
    for _ in range(iterations):
        encoded = orjson.dumps(data)
        decoded = orjson.loads(encoded)
    elapsed = time.perf_counter() - start

    print(f"library=orjson payload={payload_path} iterations={iterations} "
          f"elapsed_s={elapsed:.4f}")


if __name__ == "__main__":
    main()