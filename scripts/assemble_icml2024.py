#!/usr/bin/env python3
"""
Assemble ICML 2024 pdf-verify results from carry-pending.json and subagent checkpoints (m801-m815).
"""
import glob
import json
import os
import sys
from pathlib import Path

def main():
    stage_root = Path(".tmp/ml-harvest-600")
    venue = "icml"
    year = 2024
    verify_dir = stage_root / venue / str(year) / "pdf-verify"
    batches_dir = verify_dir / "batches"
    results_dir = verify_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    carry_file = verify_dir / "carry-pending.json"
    
    if not carry_file.exists():
        print(f"Error: {carry_file} does not exist.")
        sys.exit(1)
        
    carry_pending = json.loads(carry_file.read_text(encoding="utf-8"))
    
    # 1. Load all drafts from m801 to m815
    drafts = {} # task_id -> (result, model)
    bad_files = []
    normalized_names = 0
    
    for m in range(1, 16):
        chunk_dir = Path(f"ai_temp/pdf-affiliation-verification/haiku-v7-icml2024-m8{m:02d}-20261120")
        if not chunk_dir.exists():
            continue
        paper_files = sorted(chunk_dir.glob("paper-*.json"))
        for pf in paper_files:
            try:
                pdata = json.loads(pf.read_text(encoding="utf-8"))
            except Exception as e:
                bad_files.append((str(pf), f"JSON parse error: {e}"))
                continue
                
            task = pdata.get("task", {})
            res = pdata.get("result", {})
            task_id = res.get("task_id") or task.get("task_id")
            if not task_id:
                bad_files.append((str(pf), "Missing task_id"))
                continue
                
            # Align author names exactly with task
            expected_authors = task.get("authors", [])
            res_authors = res.get("authors", [])
            for i, name in enumerate(expected_authors):
                if i < len(res_authors):
                    if res_authors[i].get("name") != name:
                        res_authors[i]["name"] = name
                        normalized_names += 1
                        
            model = pdata.get("model", "gemini-3.8-flash")
            drafts[task_id] = (res, model)
            
    print(f"Loaded {len(drafts)} valid drafts from m801-m815. Bad files: {len(bad_files)}. Names aligned: {normalized_names}.")
    if bad_files:
        for bf, err in bad_files[:10]:
            print(f"  BAD: {bf} -> {err}")
            
    # 2. Check assembly across all batches
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
                # Align author names in carried results too
                for i, name in enumerate(t.get("authors", [])):
                    if i < len(c_res.get("authors", [])):
                        c_res["authors"][i]["name"] = name
                batch_results.append(c_res)
                models_used.add("carried")
                total_tasks_found += 1
            elif tid in drafts:
                d_res, d_mod = drafts[tid]
                # Align author names exactly with the batch task
                for i, name in enumerate(t.get("authors", [])):
                    if i < len(d_res.get("authors", [])):
                        if d_res["authors"][i].get("name") != name:
                            d_res["authors"][i]["name"] = name
                            normalized_names += 1
                batch_results.append(d_res)
                models_used.add(d_mod)
                total_tasks_found += 1
            else:
                missing_tasks.append(tid)
                
        if not missing_tasks:
            # All tasks found for this batch!
            out_file = results_dir / batch_name
            out_data = {
                "batch": batch_name,
                "model": "+".join(sorted(models_used)) or "gemini-3.8-flash",
                "via": "subagent:pdf-affiliation-verifier",
                "results": batch_results
            }
            out_file.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
            assembled_batches += 1
        else:
            incomplete_batches.append((batch_name, len(missing_tasks), len(tasks)))
            
    print(f"\nAssembly Progress:")
    print(f"  Tasks: {total_tasks_found} / {total_tasks_needed} ({total_tasks_found/total_tasks_needed*100:.1f}%)")
    print(f"  Batches assembled: {assembled_batches} / {len(carry_pending)}")
    if incomplete_batches:
        print(f"  Incomplete batches: {len(incomplete_batches)}")
        for bname, n_miss, n_tot in incomplete_batches[:5]:
            print(f"    {bname}: missing {n_miss}/{n_tot}")
            
if __name__ == "__main__":
    main()
