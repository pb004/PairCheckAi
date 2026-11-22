"""Run:  python peek_cdci.py "C:\\path\\to\\folder_with_the_downloaded_files"
Prints each data file's name, row count, column names and first 3 rows, so the brand-name step can be built.
Nothing is changed or uploaded."""
import csv
import os
import sys

folder = sys.argv[1] if len(sys.argv) > 1 else "."
for root, _, files in os.walk(folder):
    for name in sorted(files):
        path = os.path.join(root, name)
        low = name.lower()
        if low.startswith("license"):
            print(f"\nLICENSE FILE FOUND: {path}\n  Read it before using this data in your project.")
            continue
        if not low.endswith((".txt", ".tsv", ".csv")):
            continue
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            rows = list(csv.reader(f, delimiter="\t"))
        print(f"\n=== {name}   ({max(len(rows) - 1, 0)} data rows)")
        if rows:
            print("  Columns:", " | ".join(rows[0]))
        for r in rows[1:4]:
            print("  Row:", " | ".join(c[:60] for c in r))
