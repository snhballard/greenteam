"""
trivial_sleep.py

The simplest possible workload: does nothing but sleep for a fixed time.
Used only to confirm EnergiBridge starts, samples, and stops cleanly, and
to see what "doing nothing" looks like in the power trace (your idle/
baseline reference).

Usage:
    python3 trivial_sleep.py
"""

import time

print("sleeping for 5 seconds...")
time.sleep(5)
print("done")