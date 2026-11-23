#!/usr/bin/env python3
"""Credit-prioritized, restart-safe queue extractor for unreviewed map rows.

Relies directly on data/affiliation-map.csv statuses (auto/review/unmatched vs
manual/adjudicated:*) so no external shard state is required. Pre-fetches top
candidate institutions locally for zero-tool-loop batch adjudication.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adjudication  # noqa: E402
import affiliation_evidence as ae  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_unreviewed(row, scope):
    """Return True when a row belongs to scope and has not been adjudicated."""
    status = row.get("status", "")
    via = row.get("matched_via", "")
    if status == "manual" or via.startswith("adjudicated:"):
        return False
    if scope in ("auto-no-ev", "auto-flagged", "auto-edu"):
        return status == "auto" and row.get("institution_type") == "education"
    if scope == "auto-all":
        return status == "auto"
    if scope == "review":
        return status == "review"
    if scope == "unmatched":
        return status in ("unmatched", "review")
    raise ValueError(f"Unknown scope: {scope}")


def row_risk_flags(row, by_id, name_index):
    """Return list of automated risk flags for an education row."""
    raw = row["raw_affiliation"]
    iid = adjudication.full_id(row.get("institution_id", ""))
    inst = by_id.get(iid)
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
    return flags


def select_candidates(rows, by_id, name_index, share, scope, credited_only=False):
    """Filter unreviewed rows by scope and return [(weight, flags, row), ...] sorted."""
    selected = []
    for r in rows:
        if not is_unreviewed(r, scope):
            continue
        w = share.get(r["raw_affiliation"], 0.0)
        if credited_only and w <= 0.0:
            continue
        flags = row_risk_flags(r, by_id, name_index)
        if scope == "auto-no-ev" and "no_evidence" not in flags and "country_contradiction" not in flags and "company_cue" not in flags:
            continue
        if scope == "auto-flagged" and not flags:
            continue
        selected.append((w, flags, r))
    selected.sort(key=lambda item: (-item[0], adjudication.row_key(item[2]["raw_affiliation"])))
    return selected


def format_batch_item(weight, flags, row, by_id, cand_index, include_current=True):
    """Build a compact JSON record with pre-fetched candidates for LLM review."""
    raw = row["raw_affiliation"]
    item = {
        "key": adjudication.row_key(raw),
        "raw_affiliation": raw,
        "credit_weight": round(weight, 4),
        "status": row.get("status", ""),
        "flags": flags,
        "candidates": [
            {
                "id": adjudication.short_id(c["institution_id"]),
                "name": c["name"],
                "country": c.get("country", ""),
                "type": c.get("type", ""),
            }
            for c in adjudication.candidates_for(raw, by_id, cand_index, limit=5)
        ],
    }
    if include_current and row.get("institution_id"):
        iid = adjudication.full_id(row["institution_id"])
        inst = by_id.get(iid, {})
        item["current"] = {
            "id": adjudication.short_id(iid),
            "name": inst.get("display_name") or row.get("institution_name", ""),
            "country": inst.get("country_code") or row.get("country_code", ""),
            "type": inst.get("type") or row.get("institution_type", ""),
            "score": float(row.get("score") or 0.0),
        }
    return item


def cmd_status(args):
    by_id = adjudication.load_index()
    name_index = ae.build_name_index(by_id)
    _, rows, _ = adjudication.read_map()
    _, share = adjudication.string_weights(args.cache_dir)

    counts = {
        "manual_or_adjudicated": 0,
        "auto_edu_clean": 0,
        "auto_edu_no_ev_or_risk": 0,
        "auto_nonedu": 0,
        "review": 0,
        "unmatched": 0,
    }
    credits = {k: 0.0 for k in counts}

    for r in rows:
        w = share.get(r["raw_affiliation"], 0.0)
        st = r.get("status", "")
        via = r.get("matched_via", "")
        if st == "manual" or via.startswith("adjudicated:"):
            bucket = "manual_or_adjudicated"
        elif st == "review":
            bucket = "review"
        elif st == "unmatched":
            bucket = "unmatched"
        elif st == "auto" and r.get("institution_type") == "education":
            flags = row_risk_flags(r, by_id, name_index)
            if any(fl in flags for fl in ("no_evidence", "country_contradiction", "company_cue")):
                bucket = "auto_edu_no_ev_or_risk"
            else:
                bucket = "auto_edu_clean"
        else:
            bucket = "auto_nonedu"
        counts[bucket] += 1
        credits[bucket] += w

    print(f"Total rows in map: {len(rows)}")
    for k in counts:
        print(f"  {k:<24}: {counts[k]:6d} rows ({credits[k]:9.1f} credit)")
    return 0


def cmd_next(args):
    by_id = adjudication.load_index()
    name_index = ae.build_name_index(by_id)
    cand_index = adjudication.build_candidate_index(by_id)
    _, rows, _ = adjudication.read_map()
    _, share = adjudication.string_weights(args.cache_dir)

    selected = select_candidates(
        rows, by_id, name_index, share, args.scope, credited_only=args.credited_only
    )
    batch_items = [
        format_batch_item(
            w, flags, r, by_id, cand_index, include_current=not args.blind
        )
        for w, flags, r in selected[: args.limit]
    ]
    total_credit = sum(w for w, _, _ in selected)
    batch_credit = sum(x["credit_weight"] for x in batch_items)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "scope": args.scope,
                "remaining_in_scope": len(selected),
                "remaining_credit": round(total_credit, 2),
                "batch_size": len(batch_items),
                "batch_credit": round(batch_credit, 2),
                "rows": batch_items,
            },
            handle,
            ensure_ascii=False,
            indent=1,
        )

    print(
        f"wrote {len(batch_items)} items ({batch_credit:.1f} credit) -> {args.out} "
        f"[remaining in '{args.scope}': {len(selected)} rows, {total_credit:.1f} credit]"
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Restart-safe unreviewed map queue extractor.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_stat = sub.add_parser("status", help="Show reviewed vs remaining map counts")
    p_stat.add_argument("--cache-dir", action="append", default=[], help="Cache dir(s) for credit weights")

    p_next = sub.add_parser("next", help="Extract next unreviewed batch sorted by credit")
    p_next.add_argument(
        "--scope",
        default="auto-no-ev",
        choices=["auto-no-ev", "auto-flagged", "auto-edu", "auto-all", "review", "unmatched"],
    )
    p_next.add_argument("--credited-only", action="store_true", help="Only include rows with >0 credit")
    p_next.add_argument("--limit", type=int, default=50, help="Batch size (default: 50)")
    p_next.add_argument("--blind", action="store_true", help="Omit current assignment from batch")
    p_next.add_argument("--cache-dir", action="append", default=[], help="Cache dir(s) for credit weights")
    p_next.add_argument("--out", required=True, help="Output JSON path")

    args = parser.parse_args(argv)
    if not args.cache_dir:
        args.cache_dir = [os.path.join(REPO_ROOT, "cache")]
    return cmd_status(args) if args.command == "status" else cmd_next(args)


if __name__ == "__main__":
    raise SystemExit(main())
