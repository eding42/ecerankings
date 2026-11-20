#!/usr/bin/env python3
"""Download all papers and extract first-page text across all available ML editions.

Covers:
- ICLR 2024 (2025 already completed)
- NeurIPS 2016-2025
- ICML 2016-2025
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE_ROOT = ROOT / ".tmp" / "ml-harvest-600"

EDITIONS = [
    ("iclr", 2024),
    *[("iclr", y) for y in range(2023, 2016, -1)],
    *[("neurips", y) for y in range(2025, 2015, -1)],
    *[("icml", y) for y in range(2025, 2015, -1)],
]


def run(cmd: list[str]) -> bool:
    print(f"\n>>> Running: {' '.join(cmd)}", flush=True)
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        print(f"Command returned exit code {res.returncode}", file=sys.stderr, flush=True)
        return False
    return True


import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venue", choices=("iclr", "neurips", "icml"), default=None)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--max-editions", type=int, default=None, help="Max editions to run in this invocation")
    parser.add_argument("--pdf-workers", type=int, default=12)
    args = parser.parse_args()

    t_start = time.monotonic()
    editions = [
        (v, y)
        for (v, y) in EDITIONS
        if (args.venue is None or v == args.venue)
        and (args.year is None or y == args.year)
        and (args.start_year is None or y <= args.start_year)
        and (args.end_year is None or y >= args.end_year)
    ]
    if args.max_editions:
        editions = editions[: args.max_editions]

    total = len(editions)
    for idx, (venue, year) in enumerate(editions, 1):
        print(f"\n{'=' * 60}")
        print(f"[{idx}/{total}] Processing {venue.upper()} {year}")
        print(f"{'=' * 60}", flush=True)

        # 1. Membership
        cmd_mem = [
            sys.executable,
            "pipeline/harvest_ml.py",
            "--venue",
            venue,
            "--year",
            str(year),
            "--stage-root",
            str(STAGE_ROOT),
            "--stage",
            "membership",
        ]
        if not run(cmd_mem):
            print(f"Skipping PDF stage for {venue} {year} due to membership error.", file=sys.stderr, flush=True)
            continue

        # 2. PDF Download & Text Extraction
        cmd_pdf = [
            sys.executable,
            "pipeline/harvest_ml.py",
            "--venue",
            venue,
            "--year",
            str(year),
            "--stage-root",
            str(STAGE_ROOT),
            "--stage",
            "pdf",
            "--pdf-workers",
            str(args.pdf_workers),
        ]
        if not run(cmd_pdf):
            print(f"PDF stage had errors for {venue} {year}.", file=sys.stderr, flush=True)
            continue

    elapsed = time.monotonic() - t_start
    print(f"\nAll {total} editions processed in {elapsed / 60:.1f} minutes.", flush=True)


if __name__ == "__main__":
    main()
