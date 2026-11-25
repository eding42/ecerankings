#!/usr/bin/env python3
"""Collect a school from pinned browser captures when its site refuses automated requests.

`observe` replays a directory of captured list pages (manifest.json maps each configured
list URL to a captured file and its retrieval time) through the normal observation
pipeline. The captures are recorded as `browser_dom` evidence: they carry a capture hash
and the named capture tool, never an invented HTTP status or origin response hash.
`packet` writes the audit folder for an independent judgment of those shared captures:
copies of the capture files, the pinned packet, and the exact source objects the auditor
must cite. Reconcile imports the result with `--capture-packet`.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faculty_audit as audit
import faculty_refresh as f
import faculty_store as st
from faculty_registry import canonical_url

ROOT = Path(__file__).resolve().parents[1] / 'data/faculty'


def load(captures):
    manifest = st.read(captures / 'manifest.json')
    found = {}
    for url, item in manifest['captures'].items():
        found[canonical_url(url)] = dict(url=url, file=item['file'], observed_at=item['observed_at'],
                                         body=(captures / item['file']).read_bytes(), tool=manifest['tool'])
    return found


def make_fetch(found):
    def fetch(target):
        url = target if isinstance(target, str) else target['url']
        item = found.get(canonical_url(url))
        spec = dict(method='GET', form={})
        if not item:
            return dict(url=url, request=spec, status=None, observed_at=f.now(), error='No pinned capture for this URL')
        return dict(url=item['url'], request=spec, final_url=item['url'], status=None, observed_at=item['observed_at'],
                    body=item['body'], capture_format='browser_dom', capture_tool=item['tool'])
    return fetch


def observe(args):
    found = load(args.captures)
    date = min(x['observed_at'] for x in found.values())[:10]
    ref, snapshot, review = f.observe(ROOT, args.school, date, fetch=make_fetch(found), audit_transport='handoff')
    print(json.dumps(dict(observation=ref, entries=len(snapshot['roster']), failures=len(snapshot['failures'])), indent=2))


def packet(args):
    found = load(args.captures)
    settings = st.read(ROOT / 'schools.json')['schools'][args.school]
    attempt = st.read(ROOT / 'attempts' / f'{args.school}.json')
    cand = attempt['observation']
    state = st.read(audit.state_path(ROOT, cand))
    job = st.load_ref(ROOT, state['job'])
    out = args.out
    (out / 'captures').mkdir(parents=True, exist_ok=True)
    records, sources = [], []
    for listing in settings['lists']:
        item = found[canonical_url(listing['url'])]
        sid = 'shared_' + listing['id'].replace('-', '_')
        sha = st.digest(item['body'])
        shutil.copy(args.captures / item['file'], out / 'captures' / item['file'])
        request = dict(method='GET', form={})
        records.append(dict(id=sid, url=listing['url'], response_sha256=None, observed_at=item['observed_at'], request=request,
                            capture_format='browser_dom', capture_sha256=sha, capture_tool=item['tool']))
        sources.append(dict(id=sid, url=listing['url'], observed_at=item['observed_at'], request_json=json.dumps(request),
                            locator=f"captures/{item['file']} (list '{listing['id']}')", response_sha256=None,
                            capture_format='browser_dom', capture_sha256=sha, capture_tool=item['tool']))
    pkt = dict(job_id=job['job_id'], candidate_sha256=cand['sha256'],
               capture_origin='Pinned list-page text extracted in the project owner\'s browser (Claude in Chrome) on the observation date',
               records=records)
    st.atomic_json(out / 'packet.json', pkt)
    st.atomic_json(out / 'shared-sources.json', sources)
    print(f'wrote {out}/packet.json and shared-sources.json ({len(sources)} sources)')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['observe', 'packet'])
    parser.add_argument('--school', required=True)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.action == 'packet' and not args.out:
        parser.error('packet requires --out')
    {'observe': observe, 'packet': packet}[args.action](args)


if __name__ == '__main__':
    main()
