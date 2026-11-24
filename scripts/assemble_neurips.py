#!/usr/bin/env python3
"""
Assemble NeurIPS pdf-verify results from carry-pending.json and subagent checkpoints.
Usage: python3 scripts/assemble_neurips.py <year> [stage_root]
"""
import json
import sys
from pathlib import Path

def assemble_neurips(year, stage_root=".tmp/ml-harvest-600"):
    stage_path = Path(stage_root)
    venue = "neurips"
    verify_dir = stage_path / venue / str(year) / "pdf-verify"
    batches_dir = verify_dir / "batches"
    results_dir = verify_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    carry_file = verify_dir / "carry-pending.json"
    
    if not carry_file.exists():
        print(f"Error: {carry_file} does not exist.")
        return False

    carry_pending = json.loads(carry_file.read_text(encoding="utf-8"))
    
    # Load all drafts from all matching ai_temp directories for this year
    drafts = {}
    bad_files = []
    normalized_names = 0
    
    ai_temp_root = Path("ai_temp/pdf-affiliation-verification")
    matching_dirs = sorted([d for d in ai_temp_root.iterdir() if d.is_dir() and f"neurips{year}" in d.name.lower() and "haiku-v7" in d.name.lower()])
    
    for chunk_dir in matching_dirs:
        for pf in sorted(chunk_dir.glob("paper-*.json")):
            try:
                pdata = json.loads(pf.read_text(encoding="utf-8"))
            except Exception as e:
                bad_files.append((str(pf), f"JSON parse error: {e}"))
                continue
            
            if not isinstance(pdata, dict):
                bad_files.append((str(pf), "JSON is not an object"))
                continue
            
            task = pdata.get("task", {})
            res = pdata.get("result", {})
            task_id = res.get("task_id") or task.get("task_id")
            if not task_id:
                bad_files.append((str(pf), "Missing task_id"))
                continue
                
            expected_authors = task.get("authors", [])
            res_authors = res.get("authors", [])
            for i, name in enumerate(expected_authors):
                if i < len(res_authors):
                    if res_authors[i].get("name") != name:
                        res_authors[i]["name"] = name
                        normalized_names += 1
                        
            model = pdata.get("model", "gemini-3.8-flash")
            drafts[task_id] = (res, model)
            
    print(f"[{venue}/{year}] Loaded {len(drafts)} drafts from {len(matching_dirs)} chunk dirs. Bad files: {len(bad_files)}. Names aligned: {normalized_names}.")
    
    total_tasks_needed = 0
    total_tasks_found = 0
    assembled_batches = 0
    incomplete_batches = []
    
    for item in carry_pending:
        batch_name = item["batch"]
        batch_path = batches_dir / batch_name
        batch_data = json.loads(batch_path.read_text(encoding="utf-8"))
        tasks = batch_data.get("tasks", [])
        total_tasks_needed += len(tasks)
        
        batch_results = []
        missing_tasks = []
        models_used = set()
        
        for t in tasks:
            tid = t["task_id"]
            if tid in item.get("carried", {}):
                c_res = item["carried"][tid]
                for i, name in enumerate(t.get("authors", [])):
                    if i < len(c_res.get("authors", [])):
                        c_res["authors"][i]["name"] = name
                batch_results.append(c_res)
                models_used.add("carried")
                total_tasks_found += 1
            elif tid in drafts:
                d_res, d_mod = drafts[tid]
                for i, name in enumerate(t.get("authors", [])):
                    if i < len(d_res.get("authors", [])):
                        d_res["authors"][i]["name"] = name
                batch_results.append(d_res)
                models_used.add(d_mod)
                total_tasks_found += 1
            else:
                missing_tasks.append(tid)
                
        if missing_tasks:
            incomplete_batches.append((batch_name, len(missing_tasks), missing_tasks))
            print(f"  Batch {batch_name} incomplete: missing {len(missing_tasks)} tasks")
        else:
            model_label = "gemini-3.8-flash" if "gemini-3.8-flash" in models_used else "claude-haiku-5-5"
            out_file = results_dir / batch_name
            out_data = {
                "batch": batch_name,
                "model": model_label,
                "via": "subagent:pdf-affiliation-verifier",
                "results": batch_results
            }
            out_file.write_text(json.dumps(out_data, indent=2), encoding="utf-8")
            assembled_batches += 1
            print(f"  Assembled {batch_name} ({len(batch_results)} tasks)")
            
    print(f"[{venue}/{year}] Successfully assembled {assembled_batches}/{len(carry_pending)} pending batches! Total tasks: {total_tasks_found}/{total_tasks_needed}")
    return assembled_batches == len(carry_pending)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/assemble_neurips.py <year> [stage_root]")
        sys.exit(1)
    year = int(sys.argv[1])
    stage_root = sys.argv[2] if len(sys.argv) > 2 else ".tmp/ml-harvest-600"
    success = assemble_neurips(year, stage_root)
    sys.exit(0 if success else 1)
