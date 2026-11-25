#!/usr/bin/env python3
"""Validate isolated faculty evidence without changing papers or rankings."""
import argparse
from collections import Counter
import json
from pathlib import Path

from faculty_pilot import ROOT, OUT, SCRATCH, SEED, SCHOOLS, doi_key, name_key, sha, write_json, load_tree


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_match(match, work, anchors, publisher):
    """A vendor author ID alone can never satisfy an accepted authorship link."""
    require(match.get('status') == 'accepted', 'Match has not been reviewed')
    key = (match['person_id'], match['doi'], match['evidence_source_key'])
    require(key in anchors, 'Accepted match lacks a person-specific publication anchor')
    require(doi_key(work.get('doi') or '') == match['doi'], 'Work DOI differs')
    authors = work.get('authorships') or []
    pos = match['byline_position']
    require(isinstance(pos, int) and 0 <= pos < len(authors), 'Byline position is invalid')
    author = authors[pos]
    require(author.get('author_name') == match['author_name'], 'Wrong cached author at byline position')
    require(author.get('author_id') == match.get('author_id'), 'Cached author ID differs')
    require(len(authors) == match['author_count'], 'Cached author count differs')
    ids = sorted(i['id'] for i in author.get('institutions', []) if i.get('id'))
    require(ids == match['institution_ids'], 'Publication-time institutions were changed')
    require(publisher and not publisher.get('error'), 'Publisher check is unresolved')
    require(publisher['doi'] == match['doi'], 'Publisher DOI differs')
    deposited = publisher.get('authors', [])
    require(len(deposited) == len(authors), 'Publisher and cache author counts differ')
    printed_name = (deposited[pos].get('given', '') + ' ' + deposited[pos].get('family', '')).strip()
    require(name_key(printed_name) == name_key(match['author_name']), 'Publisher has a different author at this slot')


def validate(directory, check_cache=True):
    def read(name): return json.loads((directory / name).read_text())
    people = read('roster.json')
    by_person = {r['person_id']:r for r in people}
    require(len(by_person) == len(people), 'Duplicate roster person IDs')
    require(set(r['school'] for r in people) == set(SCHOOLS), 'Active pilot is not the five US schools')
    institutions=json.loads((ROOT/'site/data/institutions.json').read_text())
    require(all(institutions['https://openalex.org/'+s[0]]['country']=='US' for s in SCHOOLS.values()), 'Pilot includes a non-US institution')
    categories = {'regular', 'affiliate', 'emeritus', 'teaching', 'research_only', 'visiting', 'uncertain'}
    sources = {s['key']:s for s in read('sources.json')}
    for filename in ['profile-sources.json', 'review-sources.json']:
        for item in read(filename):
            require(item['person_id'] in by_person, 'Profile refers to unknown person')
            sources[item['source']['key']] = item['source']
    for s in read('control-sources.json'): sources[s['key']] = s
    for r in people:
        require(r['category'] in categories, 'Unknown appointment category')
        require(r['included'] == (r['category']=='regular'), 'Inclusion/category mismatch')
        require(r['source_key'] in sources and sources[r['source_key']].get('sha256'), 'Roster source lacks successful evidence')
        require(all(r.get(k) for k in ['name','original_title','profile_url','source_locator','observed_at','decision_basis']), 'Incomplete roster fact')
        for key in r.get('decision_evidence_source_keys', []):
            require(key in sources and sources[key].get('sha256'), 'Override source is unavailable')
    for s in read('schools.json'):
        group = [r for r in people if r['school']==s['school']]
        require(s['roster_entries']==len(group), 'School entry count differs')
        require(s['categories']==dict(Counter(r['category'] for r in group)), 'Category totals differ')
        require(s['regular_count']==sum(r['included'] for r in group), 'Regular-title count differs')
        require(s.get('publishable_headcount') is None, 'Pilot must not claim a reconciled public census')

    population = read('sampling-population.json')
    expected = []
    for school in SCHOOLS:
        ranked = sorted([r for r in population if r['school']==school], key=lambda r:sha((SEED+r['person_id']).encode()))
        expected.extend(r['person_id'] for r in ranked[:3])
    require(expected==[r['person_id'] for r in read('roster-sample.json')], 'Frozen roster sample changed')
    require(len(expected)==15, 'Expected three roster controls per school')

    inventory = read('cache-inventory.json')
    if check_cache:
        for item in inventory:
            require(sha((ROOT/item['path']).read_bytes())==item['sha256'], 'Cache inventory changed: '+item['path'])

    memo = {}
    def raw_record(row):
        path=row['cache_path']
        if path not in memo: memo[path]=(ROOT/path).read_bytes().splitlines()
        raw=memo[path][row['line']-1]
        require(sha(raw)==row['record_sha256'], 'Work record changed')
        work=json.loads(raw)
        a=work['authorships'][row['byline_position']]
        require(a.get('author_name')==row['author_name'], 'Candidate byline differs')
        return work

    for filename in ['paper-candidates.json','authorship-sample.json','identifier-stress-sample.json']:
        for row in read(filename):
            require(row['sampling_key']==sha((SEED+row['work_key']+':'+str(row['byline_position'])).encode()), 'Invalid sampling key')
            raw_record(row)
    require(Counter(r['school'] for r in read('authorship-sample.json'))==Counter({s:3 for s in SCHOOLS}), 'Authorship sample must cover each school')

    anchors = {(r['person_id'],r['doi'],r['source_key']) for r in read('publication-anchors.json')}
    anchor_rows = {(r['person_id'],r['doi'],r['source_key']):r for r in read('publication-anchors.json')}
    publishers = {r['doi']:r for r in read('publisher-checks.json')}
    for publisher in publishers.values():
        sources[publisher['source']['key']] = publisher['source']
    if check_cache:
        discovery = read('discovery-run.json')
        require(sha((ROOT/discovery['input']).read_bytes())==discovery['input_sha256'], 'Aggregate discovery input changed')
    accepted=read('accepted-matches.json')
    keys=set()
    for row in accepted:
        require(row['person_id'] in by_person, 'Accepted match has unknown person')
        key=(row['person_id'],row['doi'],row['byline_position'])
        require(key not in keys, 'Duplicate accepted authorship')
        keys.add(key)
        require(row['evidence_source_key'] in sources and sources[row['evidence_source_key']].get('sha256'), 'Accepted source failed')
        source=sources[row['evidence_source_key']]
        anchor=anchor_rows.get((row['person_id'],row['doi'],row['evidence_source_key']))
        require(anchor and anchor['source_sha256']==source['sha256'], 'Anchor/source provenance differs')
        source_path=SCRATCH/(row['evidence_source_key']+'.html')
        if source_path.exists():
            tree=load_tree(row['evidence_source_key'])
            present=row['doi'] in tree.text().lower() or any(doi_key(a.attrs.get('href',''))==row['doi'] for a in tree.all('a'))
            require(present, 'Accepted DOI is absent from source snapshot')
        check_match(row,raw_record(row),anchors,publishers.get(row['doi']))
        require(row['faculty_eligible_in_pilot']==by_person[row['person_id']]['included'], 'Faculty eligibility conflated with identity')
    for filename in ['roster-sample-reviews.json','authorship-reviews.json','high-credit-reviews.json','stress-case-reviews.json','roster-reconciliation.json']:
        require(read(filename), 'Missing review decisions: '+filename)

    snapshots=0
    for key,source in sources.items():
        path=SCRATCH/(key+'.html')
        if not path.exists(): path=SCRATCH/(key+'.json')
        if path.exists() and source.get('sha256'):
            require(sha(path.read_bytes())==source['sha256'], 'Source snapshot differs: '+key)
            snapshots+=1
    replay=read('sampling-replay.json')
    require(replay['status']=='passed' and replay['before']==replay['after'], 'Sampling replay did not pass')
    outcome=dict(status='passed', scope='US ECE pilot artifact integrity; not a faculty census or ranking release',
                 roster_entries=len(people), schools=len(SCHOOLS), roster_sample=15,
                 authorship_sample=15, accepted_authorship_links=len(accepted),
                 accepted_people=len({r['person_id'] for r in accepted}),
                 accepted_without_current_faculty_confirmation=sum(not r['faculty_eligible_in_pilot'] for r in accepted),
                 source_snapshots_checked=snapshots, cache_files_checked=len(inventory) if check_cache else 0,
                 unsuccessful_review_sources=[s['url'] for s in sources.values() if s.get('error')],
                 independent_review=False, public_headcounts_approved=False)
    return outcome


def recheck_authorships(directory):
    """Revalidate accepted edges after cache changes without rewriting the pilot."""
    def read(name):return json.loads((directory/name).read_text())
    anchors={(r['person_id'],r['doi'],r['source_key']) for r in read('publication-anchors.json')}
    publishers={r['doi']:r for r in read('publisher-checks.json')}
    files={};results=[]
    for match in read('accepted-matches.json'):
        path=match['cache_path']
        if path not in files:files[path]=(ROOT/path).read_bytes().splitlines()
        raw=files[path][match['line']-1]
        try:
            check_match(match,json.loads(raw),anchors,publishers.get(match['doi']))
            status,error='passed',None
        except (ValueError,KeyError,IndexError) as exc:status,error='failed',str(exc)
        results.append(dict(person_id=match['person_id'],doi=match['doi'],status=status,error=error,
                            original_record_sha256=match['record_sha256'],current_record_sha256=sha(raw)))
    outcome=dict(observed_on='2026-11-22',
        scope='Recheck previously accepted individual authorships against current local raw records; original global cache inventory has changed and is not re-certified.',
        status='passed' if all(r['status']=='passed' for r in results) else 'failed',records=results,
        inputs={name:sha((directory/name).read_bytes()) for name in ['accepted-matches.json','publication-anchors.json','publisher-checks.json']})
    write_json(directory/'current-authorship-recheck.json',outcome)
    require(outcome['status']=='passed','Accepted authorships changed; review the saved recheck report')
    return outcome


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pilot-dir',type=Path,default=OUT)
    p.add_argument('--skip-cache-hashes',action='store_true',help='Only for local iteration; final validation must check the cache inventory')
    p.add_argument('--recheck-authorships',action='store_true',help='Recheck accepted individual edges against current cache without replacing the original inventory validation')
    a=p.parse_args()
    if a.recheck_authorships:
        outcome=recheck_authorships(a.pilot_dir)
        print(f"Rechecked {len(outcome['records'])} accepted authorships: {outcome['status']}")
        return
    outcome=validate(a.pilot_dir,not a.skip_cache_hashes)
    write_json(a.pilot_dir/'validation.json',outcome)
    print(json.dumps(outcome,indent=2))


if __name__=='__main__': main()
