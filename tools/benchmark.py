"""Reproducible synthetic benchmark. Native SQLite/OS memory is not measured."""

import argparse
import csv
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tabletrail import analyze


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.rows <= 1000000:
        parser.error("--rows must be between 1 and 1000000")
    with tempfile.TemporaryDirectory(prefix="tabletrail-bench-") as directory:
        source = Path(directory) / "synthetic.csv"
        with source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["sku", "warehouse", "quantity", "unit_price"])
            for i in range(args.rows):
                writer.writerow([f"SKU-{i:08}", ["NORTH", "SOUTH", "WEST"][i % 3], i % 250, f"{i % 500}.50"])
        tracemalloc.start()
        start = time.perf_counter()
        report = analyze(source)
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert report["rows"] == args.rows
        assert report["columns"][0]["distinct_count"] == args.rows
        print(json.dumps({"python": platform.python_version(), "platform": platform.system(),
                          "records": args.rows, "columns": 4, "seconds": round(elapsed, 3),
                          "records_per_second": round(args.rows / elapsed),
                          "peak_python_allocated_mib": round(peak / 1024**2, 3),
                          "memory_note": "tracemalloc excludes native SQLite and OS caches; one local run, not a guarantee"}, indent=2))


if __name__ == "__main__":
    main()
