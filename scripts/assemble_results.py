import glob
import json
import os
import sys
from pathlib import Path

def assemble_edition(venue, year, stage_root=".tmp/ml-harvest-600"):
    results_dir = Path(stage_root) / venue / str(year) / "pdf-verify" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    batches_dir = Path(stage_root) / venue / str(year) / "pdf-verify" / "batches"
    batch_files = sorted(batches_dir.glob("batch-*.json"))
    
    assembled_count = 0
    for bf in batch_files:
        batch_num_str = bf.name.split("-")[1]
        attempt_dirs = list(Path("ai_temp/pdf-affiliation-verification").glob(f"{venue}-{year}-b{batch_num_str}-*-attempt1"))
        if not attempt_dirs:
            continue
        attempt_dir = attempt_dirs[0]
        
        import re
        paper_files = sorted([f for f in attempt_dir.glob("paper-*.json") if re.match(r"^paper-\d+\.json$", f.name)])
        batch_data = json.loads(bf.read_text(encoding="utf8"))
        expected_tasks = batch_data.get("tasks", [])
        if len(paper_files) != len(expected_tasks):
            print(f"Skipping {bf.name}: {len(paper_files)}/{len(expected_tasks)} papers complete")
            continue
        
        results = []
        model_name = None
        for pf in paper_files:
            pdata = json.loads(pf.read_text(encoding="utf8"))
            if model_name is None:
                model_name = pdata.get("model", "claude-haiku-5-5")
            res = pdata.get("result", pdata)
            results.append(res)
            
        out_file = results_dir / bf.name
        out_data = {
            "batch": bf.name,
            "model": model_name or "claude-haiku-5-5",
            "via": "subagent:pdf-affiliation-verifier",
            "results": results
        }
        out_file.write_text(json.dumps(out_data, indent=2), encoding="utf8")
        assembled_count += 1
        print(f"Assembled {bf.name} ({len(results)} papers)")

    print(f"Finished assembling {venue} {year}: {assembled_count}/{len(batch_files)} batches ready")
    return assembled_count, len(batch_files)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/assemble_results.py <venue> <year> [stage_root]")
        sys.exit(1)
    venue = sys.argv[1]
    year = int(sys.argv[2])
    stage_root = sys.argv[3] if len(sys.argv) > 3 else ".tmp/ml-harvest-600"
    assemble_edition(venue, year, stage_root)
