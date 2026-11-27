#!/usr/bin/env python3
"""Apply reviewed, publication-specific affiliations to an isolated cache.

Every decision carries publisher evidence, the complete cached byline, and the
expected prior institution set. Native OpenAlex data is preserved in the record.
No fuzzy author match, global institution override, or implicit map precedence.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re

try:
    from . import adjudication
    from .workkey import norm_doi
except ImportError:
    import adjudication
    from workkey import norm_doi


def same_paper(work, decision):
    """Match by DOI, or by the exact cached record id for a paper without one."""
    if decision.get('doi'):
        return norm_doi(work.get('doi')) == norm_doi(decision['doi'])
    return bool(decision.get('work_id')) and work.get('id') == decision['work_id'] and not work.get('doi')


def correct(work, decision, index):
    if not same_paper(work, decision):
        raise ValueError('DOI or record id does not match correction')
    authors = work.get('authorships') or []
    if [a.get('author_name') for a in authors] != decision['author_names']:
        raise ValueError('Complete author list or order changed')
    position = decision['author_index']
    if not isinstance(position, int) or not 0 <= position < len(authors):
        raise ValueError('Invalid author position')
    if not decision.get('source_url') or not decision.get('evidence') or not decision.get('raw_affiliations'):
        raise ValueError('Publisher evidence and printed affiliations are required')
    fingerprint = hashlib.sha256(json.dumps(decision, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if authors[position].get('affiliation_correction', {}).get('decision_sha256') == fingerprint:
        return work, False
    prior = authors[position].get('institutions') or []
    if sorted(i['id'] for i in prior) != sorted(decision['expected_institution_ids']):
        raise ValueError('Prior institution set changed; review again')
    replacement = []
    for iid in decision['institution_ids']:
        if iid not in index:
            raise ValueError(f'Institution absent from evidenced index: {iid}')
        institution = index[iid]
        replacement.append({k: institution[k] for k in ('id', 'display_name', 'type', 'country_code', 'lineage')})
    if not replacement or len({i['id'] for i in replacement}) != len(replacement):
        raise ValueError('Correction requires distinct evidenced institutions')
    result = copy.deepcopy(work)
    author = result['authorships'][position]
    author['affiliation_correction'] = {'decision_sha256': fingerprint,
                                      'source_url': decision['source_url'], 'evidence': decision['evidence'],
                                      'prior_institutions': prior,
                                      'prior_raw_affiliations': author.get('raw_affiliations') or []}
    author['institutions'] = replacement
    author['raw_affiliations'] = decision['raw_affiliations']
    author['affiliation_source'] = 'publisher-correction'
    return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--decisions', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='otherwise validate without changing cache')
    args = parser.parse_args()
    if args.apply and args.cache_dir.resolve() == (Path(__file__).resolve().parents[1] / 'cache').resolve():
        parser.error('Apply to an isolated candidate cache, then use promote_release.py')
    decisions = [json.loads(line) for line in args.decisions.read_text().splitlines() if line.strip()]
    index = adjudication.load_index()
    pending = {}
    changed = 0
    for decision in decisions:
        if not re.fullmatch(r'[a-z0-9-]+', decision['venue']) or not re.fullmatch(r'\d{4}', str(decision['year'])):
            raise ValueError('Invalid venue/year path')
        path = args.cache_dir / decision['venue'] / str(decision['year']) / 'works.jsonl'
        if path not in pending:
            pending[path] = [json.loads(line) for line in path.read_text().splitlines()]
        rows = pending[path]
        matches = [i for i, w in enumerate(rows) if same_paper(w, decision)]
        if len(matches) != 1:
            raise ValueError('Correction must match exactly one cached paper')
        i = matches[0]
        rows[i], applied = correct(rows[i], decision, index)
        changed += applied
    if args.apply:
        for path, rows in pending.items():
            temp = path.with_name(path.name + '.correction-tmp')
            temp.write_text(''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n' for row in rows))
            os.replace(temp, path)
    print(json.dumps({'decisions': len(decisions), 'changed_authorships': changed, 'applied': args.apply}))


if __name__ == '__main__':
    main()
