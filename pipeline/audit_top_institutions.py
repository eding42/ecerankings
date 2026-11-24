#!/usr/bin/env python3
"""Extract Precision and Recall audit queues for the top-N ranked institutions.

Read-only: inspects the affiliation map, institution index, and cached works
to produce prioritized JSON queues and a Markdown summary for the top-N
institutions in a field. Does not modify the map or cache.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adjudication  # noqa: E402
import affiliation_evidence as ae  # noqa: E402
from fields import add_field_argument, get_field  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def compute_top_institutions(field_cfg, data_dir, top_n, by_id, country=None):
    """Rank institutions by geometric mean of (1 + area_credit) over default_on areas."""
    with open(field_cfg.areas_path, encoding="utf-8") as handle:
        areas = json.load(handle)["areas"]
    default_areas = sorted(k for k, v in areas.items() if v.get("default_on"))
    n_areas = len(default_areas)
    if n_areas == 0:
        raise ValueError(f"No default_on areas found for field {field_cfg.id}")

    inst_area = defaultdict(lambda: defaultdict(float))
    inst_names = {}
    csv_path = os.path.join(data_dir, "inst-area-year.csv")
    with open(csv_path, newline="", encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            yr = int(r["year"])
            iid = adjudication.full_id(r["institution_id"])
            if country:
                info = by_id.get(iid)
                if not info or info.get("country_code") != country:
                    continue
            if (
                field_cfg.default_start_year <= yr <= field_cfg.default_end_year
                and r["area"] in default_areas
            ):
                inst_area[iid][r["area"]] += float(r["adjusted_count"])
                inst_names[iid] = r["institution_name"]

    scores = []
    for iid, amap in inst_area.items():
        prod = 1.0
        for ak in default_areas:
            prod *= 1.0 + amap.get(ak, 0.0)
        gmean = prod ** (1.0 / n_areas) - 1.0
        scores.append((gmean, iid, inst_names[iid]))

    scores.sort(reverse=True)
    return [
        {"rank": i, "score": sc, "institution_id": iid, "institution_name": name}
        for i, (sc, iid, name) in enumerate(scores[:top_n], 1)
    ]


def build_top_matchers(top_list, by_id):
    """Build folded full-name regexes for each top-N institution for recall scanning."""
    matchers = {}
    for entry in top_list:
        iid = entry["institution_id"]
        inst = by_id.get(iid)
        if not inst:
            continue
        names = set()
        for raw_name in [inst.get("display_name", "")] + (inst.get("alternatives") or []):
            folded = ae.fold(raw_name)
            # Only use distinctive multi-word names (>= 12 chars) for recall scanning
            if len(folded) >= 12 and len(folded.split()) >= 2:
                names.add(folded)
        if names:
            pattern = re.compile(
                r"\b(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b"
            )
            matchers[iid] = pattern
    return matchers


def inspect_precision_flags(row, inst, name_index):
    """Return list of suspect flags for a row mapped to a top-N institution."""
    raw = row["raw_affiliation"]
    flags = []
    if not inst or not ae.institutional_name_evidence(raw, inst, name_index):
        flags.append("no_evidence")
    if inst and ae.country_contradiction(raw, inst.get("country_code", "")):
        flags.append("country_contradiction")
    if inst and ae.names_other_university(raw, inst, name_index):
        flags.append("names_other_uni")
    if ae.looks_like_company(raw):
        flags.append("company_cue")
    if float(row.get("score") or 0.0) < 0.90:
        flags.append("low_score")
    if row.get("status") == "review":
        flags.append("review")
    return flags


def run_audit(field_cfg, top_n, data_dir, cache_dir, out_dir, country=None):
    by_id = adjudication.load_index()
    top_list = compute_top_institutions(field_cfg, data_dir, top_n, by_id, country=country)
    top_by_id = {e["institution_id"]: e for e in top_list}

    name_index = ae.build_name_index(by_id)
    _, rows, _ = adjudication.read_map()
    counts, share = adjudication.string_weights([cache_dir])
    matchers = build_top_matchers(top_list, by_id)

    precision_queue = []
    recall_queue = []
    per_inst = {
        e["institution_id"]: {
            **e,
            "total_rows": 0,
            "total_credit": 0.0,
            "clean_rows": 0,
            "clean_credit": 0.0,
            "suspect_rows": 0,
            "suspect_credit": 0.0,
            "recall_rows": 0,
            "recall_credit": 0.0,
        }
        for e in top_list
    }

    for r in rows:
        raw = r["raw_affiliation"]
        members = [adjudication.full_id(m) for m in adjudication.ids_of(r.get("institution_id", ""))]
        # A joint row splits its credit evenly; account each member's share.
        w = share.get(raw, 0.0) / max(1, len(members))
        c = counts.get(raw, 0)
        in_top = [m for m in members if m in top_by_id]
        iid = in_top[0] if in_top else (members[0] if members else "")
        for extra in in_top[1:]:
            per_inst[extra]["total_rows"] += 1
            per_inst[extra]["total_credit"] += w
            per_inst[extra]["clean_rows"] += 1
            per_inst[extra]["clean_credit"] += w

        if iid in top_by_id:
            st = per_inst[iid]
            st["total_rows"] += 1
            st["total_credit"] += w
            inst = by_id.get(iid)
            flags = inspect_precision_flags(r, inst, name_index)
            if flags:
                st["suspect_rows"] += 1
                st["suspect_credit"] += w
                precision_queue.append({
                    "key": adjudication.row_key(raw),
                    "raw_affiliation": raw,
                    "credit_weight": round(w, 4),
                    "occurrences": c,
                    "status": r.get("status", ""),
                    "score": float(r.get("score") or 0.0),
                    "mapped_id": iid,
                    "mapped_name": r.get("institution_name", ""),
                    "mapped_type": r.get("institution_type", ""),
                    "flags": flags,
                })
            else:
                st["clean_rows"] += 1
                st["clean_credit"] += w
            continue

        # Recall scan: raw string not mapped to top-N, check if it names one
        folded_raw = ae.fold(raw)
        if not folded_raw:
            continue
        mapped_inst = by_id.get(iid) if iid else None
        mapped_has_ev = (
            ae.institutional_name_evidence(raw, mapped_inst, name_index)
            if mapped_inst
            else False
        )
        for target_iid, pat in matchers.items():
            if pat.search(folded_raw):
                st = per_inst[target_iid]
                st["recall_rows"] += 1
                st["recall_credit"] += w
                recall_queue.append({
                    "key": adjudication.row_key(raw),
                    "raw_affiliation": raw,
                    "credit_weight": round(w, 4),
                    "occurrences": c,
                    "status": r.get("status", ""),
                    "current_id": iid,
                    "current_name": r.get("institution_name", ""),
                    "current_type": r.get("institution_type", ""),
                    "current_has_evidence": mapped_has_ev,
                    "candidate_top_id": target_iid,
                    "candidate_top_name": top_by_id[target_iid]["institution_name"],
                })

    precision_queue.sort(key=lambda x: x["credit_weight"], reverse=True)
    recall_queue.sort(key=lambda x: (not x["current_has_evidence"], x["credit_weight"]), reverse=True)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "precision_queue.json"), "w", encoding="utf-8") as handle:
        json.dump(precision_queue, handle, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "recall_queue.json"), "w", encoding="utf-8") as handle:
        json.dump(recall_queue, handle, ensure_ascii=False, indent=1)

    summary_rows = [per_inst[e["institution_id"]] for e in top_list]
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary_rows, handle, ensure_ascii=False, indent=1)

    lines = [
        f"# Top {top_n} {field_cfg.short_name} Affiliation Audit Scope",
        "",
        "| Rank | Institution | Total Rows | Clean | Suspect (Precision) | Suspect Credit | Recall Candidates | Recall Credit |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in summary_rows:
        lines.append(
            f"| {s['rank']} | {s['institution_name']} | {s['total_rows']} | {s['clean_rows']} | "
            f"{s['suspect_rows']} | {s['suspect_credit']:.1f} | {s['recall_rows']} | {s['recall_credit']:.1f} |"
        )
    lines += [
        "",
        f"**Precision Queue:** {len(precision_queue)} rows ({sum(x['credit_weight'] for x in precision_queue):.1f} credit) -> `precision_queue.json`",
        f"**Recall Queue:** {len(recall_queue)} rows ({sum(x['credit_weight'] for x in recall_queue):.1f} credit) -> `recall_queue.json`",
    ]
    md_path = os.path.join(out_dir, "summary.md")
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    print("\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit top-N ranked institutions in the affiliation map.")
    add_field_argument(parser)
    parser.add_argument("--top", type=int, default=20, help="Number of top institutions to audit (default: 20)")
    parser.add_argument("--country", help="Optional ISO country code filter (e.g. US)")
    parser.add_argument("--data-dir", help="Aggregate data directory (default: field's site_data_dir)")
    parser.add_argument("--cache-dir", help="Cache directory (default: field's cache_dir)")
    parser.add_argument("--out", default="data/refresh/top20-ece-audit", help="Output directory")
    args = parser.parse_args(argv)

    field_cfg = get_field(args.field)
    data_dir = args.data_dir or field_cfg.site_data_dir
    cache_dir = args.cache_dir or field_cfg.cache_path
    run_audit(field_cfg, args.top, data_dir, cache_dir, args.out, country=args.country)


if __name__ == "__main__":
    main()
