#!/usr/bin/env python3
"""Run verify-prep (600 DPI) and stage batches for specified or remaining editions."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

STAGE_ROOT = Path(".tmp/ml-harvest-600")

ALL_NEURIPS = [("neurips", y) for y in range(2016, 2026)]

def stage_batches(venue, year, stage_root=STAGE_ROOT):
    batches_dir = Path(stage_root) / venue / str(year) / "pdf-verify" / "batches"
    if not batches_dir.exists():
        print(f"No batches dir at {batches_dir}")
        return []
    
    staged = []
    batch_files = sorted(batches_dir.glob("batch-*.json"))
    for b_path in batch_files:
        b_data = json.loads(b_path.read_text())
        b_num = int(b_path.name.split("-")[1])
        tasks = b_data["tasks"]
        author_count = sum(len(t["authors"]) for t in tasks)
        
        target_dir = Path("ai_temp/pdf-affiliation-verification") / f"{venue}-{year}-b{b_num:04d}-claude-haiku-5-5-attempt1"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_batch_file = target_dir / b_path.name
        shutil.copy2(b_path, target_batch_file)
        
        sha256 = hashlib.sha256(b_path.read_bytes()).hexdigest()
        
        run_info = {
            "batch": str(target_batch_file),
            "batch_sha256": sha256,
            "model": "claude-haiku-5-5",
            "mechanism": "delegate_task:claudeAgent_usc",
            "venue": venue,
            "year": int(year),
            "batch_number": b_num,
            "task_count": len(tasks),
            "author_count": author_count
        }
        (target_dir / "run.json").write_text(json.dumps(run_info, indent=2))
        staged.append((target_dir, run_info))
    print(f"[{venue}/{year}] Staged {len(staged)} batches into ai_temp/pdf-affiliation-verification/")
    return staged

def run_edition(venue, year, workers=8):
    t0 = time.time()
    print(f"\nPrepping {venue} {year} at 600 DPI ...", flush=True)
    cmd = [
        sys.executable,
        "pipeline/harvest_ml.py",
        "--venue", venue,
        "--year", str(year),
        "--stage", "verify-prep",
        "--verify-sample", "50",
        "--pdf-workers", str(workers),
        "--stage-root", str(STAGE_ROOT),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(res.stdout, flush=True)
    if res.returncode != 0:
        print(f"ERROR: verify-prep failed for {venue} {year} with return code {res.returncode}", file=sys.stderr)
        return False
    
    stage_batches(venue, year)
    dt = time.time() - t0
    print(f"[{venue}/{year}] Finished in {dt:.1f}s", flush=True)
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--venue", default="neurips")
    parser.add_argument("--years", nargs="+", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    years = args.years or list(range(2016, 2026))
    for y in years:
        run_edition(args.venue, y, workers=args.workers)

if __name__ == "__main__":
    main()
