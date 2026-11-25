#!/usr/bin/env python3
"""Reconcile one school's primary review with its imported independent audit, then accept.

Primary decisions come from the official directory titles and list categories
(`dry` prints any disagreement with the audit without changing data). `accept`
imports the audit result with its execution receipt, fetches the cited official
profile pages as immutable supplemental evidence, writes the explicit decisions
into the pending review and runs the deterministic acceptance gate. A disagreement
between primary and audit decisions blocks acceptance unless explicitly allowed;
the audit gate still rejects unresolved decisions and blocking findings.

Per-school overrides (JSON): {"Person Name": {"profile_urls": [...], "note": "..."}}
add evidence and reasons for named people; they never change a decision.
List role hints live in schools.json as `role_hint` on a list (emeritus, adjunct,
joint, teaching).
"""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faculty_audit as audit
import faculty_refresh as f
import faculty_store as st
from faculty_registry import stable_id

ROOT = Path(__file__).resolve().parents[1] / 'data/faculty'


def primary_decision(title, list_hint):
    """Conservative title rules. Anything they cannot decide stays unresolved."""
    t = title.lower()
    if list_hint == 'emeritus' or 'emerit' in t:
        return 'excluded', 'emeritus', 'not_in_core'
    if any(k in t for k in ('adjunct', 'visiting', 'affiliate research')):
        return 'excluded', 'visiting' if 'visiting' in t else 'adjunct', 'not_in_core'
    if 'professor of practice' in t or 'professor of the practice' in t or 'teaching' in t or 'clinical' in t:
        return 'excluded', 'academic_professional', 'not_in_core'
    if any(k in t for k in ('lecturer', 'instructor')):
        return 'excluded', 'teaching', 'not_in_core'
    if any(k in t for k in ('research professor', 'research scientist', 'research associate', 'postdoc')):
        return 'excluded', 'research_only', 'not_in_core'
    if list_hint == 'joint' or (('joint' in t or 'secondary' in t) and 'professor' in t):
        return 'included', 'joint_secondary', 'current'
    if 'affiliated' in t and 'professor' in t:
        return 'included', 'affiliate_professor', 'current'
    if 'courtesy' in t:
        return 'included', 'courtesy', 'current'
    if 'professor' in t:
        return 'included', 'regular', 'current'
    return 'unresolved', 'unresolved', 'unknown'


def fetch_supplemental(url, observed_on):
    result = f.get_url(url)
    if result.get('error') or result.get('status') != 200 or result['observed_at'][:10] != observed_on:
        raise ValueError(f'Supplemental fetch failed or is not from the observation date: {url}')
    body = result['body']
    sha = st.digest(body)
    evidence = dict(url=result['url'], final_url=result.get('final_url', result['url']), observed_at=result['observed_at'],
                    http_status=200, response_sha256=sha, **f.projection(body, result['url']))
    ref = st.put(ROOT, 'evidence', evidence)
    sid = stable_id('source', f.request_key(result) + ':' + sha)
    source = dict(id=sid, url=result['url'], final_url=result.get('final_url', result['url']), response_sha256=sha,
                  observed_at=result['observed_at'], http_status=200, kind='official_university_profile',
                  assertion_origin='university', upstream_source_ids=[], provenance_independence='not_assumed', evidence=ref)
    return dict(source=source, evidence=ref), sid


def run(args):
    attempt = st.read(ROOT / 'attempts' / f'{args.school}.json')
    cand = attempt['observation']
    snap = st.load_ref(ROOT, cand)
    policy = st.read(ROOT / 'policy.json')
    settings = st.read(ROOT / 'schools.json')['schools'][args.school]
    result = st.read(args.result)
    audit_by_person = {r['person_id']: r for r in result['records']}
    overrides = st.read(args.overrides) if args.overrides else {}
    hints = {x['id']: x.get('role_hint') for x in settings['lists']}
    list_url = {x['id']: x['url'] for x in settings['lists']}
    source_by_url = {audit.canonical(s['url']): s['id'] for s in snap['sources']}
    list_of = {}
    for lid, rows in snap['lists'].items():
        for row in rows:
            list_of.setdefault(row.get('entry_id') or row['profile_url'], []).append(lid)
    roster_by_key = {}
    for row in snap['roster']:
        roster_by_key[row.get('entry_id') or row['profile_url']] = row
    rows = []
    for person in snap['people']:
        key = (person.get('directory_entry_ids') or [None])[0] or person['profile_urls'][0]
        row = roster_by_key[key]
        # People added from configured supplemental profiles are on no list page: attribute them to the primary list.
        lists = list_of.get(key) or [next(x['id'] for x in settings['lists'] if x.get('primary'))]
        # The primary roster list takes precedence; otherwise use the first list the person appears on.
        primary_id = next((x['id'] for x in settings['lists'] if x['id'] in lists and x.get('primary')), lists[0])
        decisions = [(lid, primary_decision(row['title'], hints.get(lid))) for lid in lists]
        lid, (status, category, state) = next(((a, b) for a, b in decisions if a == primary_id), decisions[0])
        for other, value in decisions:  # an excluded category on any list wins over inclusion
            if value[0] == 'excluded' and status == 'included':
                lid, (status, category, state) = other, value
        rows.append((person, row, lid, status, category, state))
    differences = []
    for person, row, lid, status, category, state in rows:
        a = audit_by_person[person['id']]
        audited_state = 'not_in_core' if a['decision'] == 'excluded' else a['current_state']
        if (status, category, state) != (a['decision'], a['category'], audited_state):
            differences.append((person['display_name'], row['title'][:70], lid, (status, category, state),
                                (a['decision'], a['category'], a['current_state'])))
    print(f'{args.school}: {len(rows)} people; primary decisions differ from the audit for {len(differences)}')
    for item in differences:
        print('  ', item)
    unresolved = [r['person_id'] for r in result['records'] if r['decision'] == 'unresolved']
    print(f'audit unresolved: {len(unresolved)}; audit statuses:',
          {k: sum(1 for r in result['records'] if r['decision'] == k) for k in ('included', 'excluded', 'unresolved')})
    if args.mode == 'dry':
        return
    if differences and not args.accept_audit_differences:
        raise SystemExit('Primary decisions differ from the audit; review them and pass --accept-audit-differences if the audit is right')
    profile_urls = set(args.profile_url)
    for info in overrides.values():
        profile_urls.update(info.get('profile_urls', []))
    auto_profiles = {}
    if args.profiles_from_audit:
        # Cite the official pages the auditor downloaded for a person; each is re-fetched
        # on the observation date as immutable supplemental evidence.
        list_canonical = {audit.canonical(x['url']) for x in settings['lists']}
        urls = {s['id']: s['url'] for s in result['sources']}
        for record in result['records']:
            found = [urls[i] for i in record['source_ids'] if audit.canonical(urls[i]) not in list_canonical]
            if found:
                auto_profiles[record['person_id']] = found
                profile_urls.update(found)
    supplemental, extra = [], {}
    for url in sorted(profile_urls):
        https_url = 'https://' + url.split('://', 1)[1] if url.startswith('http://') else url
        try:
            item, sid = fetch_supplemental(https_url, snap['observed_on'])
        except ValueError as exc:
            print('WARNING: profile not cited as supplemental evidence:', exc)
            continue
        supplemental.append(item)
        extra[audit.canonical(url)] = sid
    decisions = []
    for person, row, lid, status, category, state in rows:
        a = audit_by_person[person['id']]
        appt = copy.deepcopy(next(x for x in person['appointments'] if x['institution_id'] == snap['institution_id']))
        info = overrides.get(person['display_name'], {})
        sids = [source_by_url[audit.canonical(list_url[lid])]] + [extra[audit.canonical(u)] for u in info.get('profile_urls', []) + auto_profiles.get(person['id'], []) if audit.canonical(u) in extra]
        reason = f"Official {settings['name']} {settings['unit']} {lid} listing: {row['title']}."
        if info.get('note'):
            reason += ' ' + info['note']
        appt.update(category=a['category'], membership=a['membership'], current_state=a['current_state'],
                    effective_from=json.loads(a['effective_from_json']), effective_to=None)
        appt['decision'].update(status=a['decision'], reason=reason, policy_id=policy['id'], source_ids=sorted(set(sids)),
                                reviewers=[args.reviewer, result['reviewer_id']], independently_reviewed=True)
        claims = [dict(id=stable_id('claim', person['id'] + ':v5-title'), property='appointment_detail',
                       value=f"{row['title']} [{lid} list]", state='supported', source_ids=sorted(set(sids)),
                       locator='Official directory listing and cited profile'),
                  dict(id=stable_id('claim', person['id'] + ':v5-membership'), property='department_membership',
                       value=settings['unit'] if a['membership'] == 'ece' else f"Non-ECE ({a['membership']})",
                       state='supported', source_ids=sorted(set(sids)), locator='Official directory listing')]
        decisions.append(dict(person_id=person['id'], appointment=appt, claims=claims))
    state = st.read(audit.state_path(ROOT, cand))
    job = st.load_ref(ROOT, state['job'])
    receipt = dict(job_id=job['job_id'], candidate_sha256=cand['sha256'], transport='t3', run_id=args.run_id,
                   model=args.model, finished_at=audit.utcnow(), exit_code=0)
    if args.capture_packet:
        # Independent judgment of pinned shared browser captures (sites that refuse automated downloads).
        receipt.update(review_mode='independent_judgment_of_shared_captures',
                       capture_packet=st.put(ROOT, 'audits/packets', st.read(args.capture_packet)))
    audit.import_result(ROOT, cand, result, receipt)
    review_path = ROOT / 'pending-reviews' / Path(cand['file']).name
    review = st.read(review_path)
    review.update(reviewer=args.reviewer, independent_reviewer=result['reviewer_id'], rationale=args.rationale,
                  crosschecks_reviewed=True, decisions=decisions, supplemental_sources=supplemental,
                  independent_review_scope=f"Full-roster independent audit of {len(result['records'])} directory entries.")
    st.atomic_json(review_path, review)
    print('draft statuses:', f.review_draft(ROOT, review_path)[1])
    print('accepted:', f.accept_review(ROOT, review_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=['dry', 'accept'])
    parser.add_argument('--school', required=True)
    parser.add_argument('--result', type=Path, required=True, help='Independent audit result JSON')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--model', default='')
    parser.add_argument('--reviewer', default='Claude Sonnet 5.5 (primary)')
    parser.add_argument('--rationale', default='Primary review of every directory entry from the official department pages, reconciled with a full-roster independent audit.')
    parser.add_argument('--overrides', type=Path)
    parser.add_argument('--profile-url', action='append', default=[])
    parser.add_argument('--profiles-from-audit', action='store_true',
                        help='Re-fetch and cite the non-list official pages the auditor cited for each person')
    parser.add_argument('--accept-audit-differences', action='store_true')
    parser.add_argument('--capture-packet', type=Path, help='Pinned capture packet (faculty_capture.py packet) for a browser-capture audit')
    args = parser.parse_args()
    if args.mode == 'accept' and not (args.run_id and args.model):
        parser.error('accept requires --run-id and --model from the audit execution')
    run(args)


if __name__ == '__main__':
    main()
