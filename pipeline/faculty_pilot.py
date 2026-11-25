#!/usr/bin/env python3
"""Collect isolated faculty pilot evidence; never write ranking inputs or outputs.

Stdlib only. Downloaded HTML is scratch; permanent records retain factual name,
title, source locator, observation time and response hash. No contact details.
"""
import argparse
from collections import Counter
from collections import defaultdict
import csv
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/faculty-pilot/2026-11-22'
SCRATCH = ROOT / '.tmp/faculty-pilot'
SEED = 'faculty-pilot-2026-11-22-v1'
SCHOOLS = {
    'berkeley': ('I95457486', 'UC Berkeley', 'Electrical Engineering within EECS'),
    'illinois': ('I157725225', 'Illinois Urbana-Champaign', 'Electrical and Computer Engineering'),
    'stanford': ('I97018004', 'Stanford University', 'Electrical Engineering'),
    'texas': ('I86519309', 'University of Texas at Austin', 'Electrical and Computer Engineering'),
    'gatech': ('I130701444', 'Georgia Institute of Technology', 'Electrical and Computer Engineering'),
}
URLS = {
    'berkeley': 'https://www2.eecs.berkeley.edu/Faculty/Lists/EE/faculty.html',
    'berkeley_current': 'https://www2.eecs.berkeley.edu/Faculty/Lists/faculty.html',
    'illinois': 'https://ece.illinois.edu/about/directory/faculty',
    'illinois_dept': 'https://ece.illinois.edu/about/directory/faculty-dept',
    'illinois_facts': 'https://ece.illinois.edu/about/rankings',
    'stanford': 'https://ee.stanford.edu/people/faculty',
    'texas': 'https://ece.utexas.edu/people/faculty',
    'texas_ece': 'https://ece.utexas.edu/people/faculty/ece',
    'texas_about': 'https://ece.utexas.edu/people',
    'gatech': 'https://ece.gatech.edu/directory/all?field_person_groups_target_id=2323',
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compact(text):
    return ' '.join(text.split())


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def all(self, tag=None, cls=None):
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if (tag is None or child.tag == tag) and (cls is None or cls in (child.attrs.get('class') or '').split()):
                yield child
            yield from child.all(tag, cls)

    def text(self):
        if self.tag in ('script', 'style'):
            return ''
        return compact(' '.join(c.text() if isinstance(c, Node) else c for c in self.children))

    def first(self, tag=None, cls=None):
        return next(self.all(tag, cls), None)


class Tree(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(n)
        if tag not in self.VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def fetch(key, url, refresh=False):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    hp, mp = SCRATCH / f'{key}.html', SCRATCH / f'{key}.meta.json'
    if mp.exists() and hp.exists() and not refresh:
        meta = json.loads(mp.read_text())
        if meta.get('url') == url and sha(hp.read_bytes()) == meta['sha256']:
            return meta
    meta = {'key': key, 'url': url, 'fetched_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ECERankings faculty research pilot (public academic research)'})
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            meta.update(final_url=response.url, status=response.status, sha256=sha(body), bytes=len(body))
            hp.write_bytes(body)
    except (urllib.error.URLError, TimeoutError) as error:
        meta.update(error=str(error), status=getattr(error, 'code', None))
        if isinstance(error, urllib.error.HTTPError):
            meta['challenge'] = error.headers.get('Cf-Mitigated')
        # Never let an older successful body be associated with a failed fetch.
        hp.unlink(missing_ok=True)
    write_json(mp, meta)
    return meta


def load_tree(key):
    return Tree((SCRATCH / f'{key}.html').read_text(errors='replace')).root


def classify(title):
    t = title.casefold()
    for pattern, category in [
        (r'emerit|prof emer\b', 'emeritus'), (r'adjunct|\badj\b|courtesy|affiliate|associated professor', 'affiliate'),
        (r'visiting|honorary', 'visiting'), (r'teaching|instructor|of practice|of instruction|lecturer', 'teaching'),
        (r'research professor|research associate|research fellow|research assistant|postdoc', 'research_only'),
    ]:
        if re.search(pattern, t):
            return category
    if re.search(r'professor|\bprof\b|reader|lecturer', t):
        return 'regular'
    return 'uncertain'


def person(school, name, title, profile, source, locator, category=None):
    # The unit's own profile locator is more durable than a normalized name.
    pid = school + ':' + sha(profile.encode())[:16]
    category = category or classify(title)
    return dict(person_id=pid, school=school, name=compact(name), original_title=compact(title),
                profile_url=profile, source_key=source, source_locator=locator,
                category=category, included=category == 'regular',
                decision_basis='Official roster title and pilot category policy',
                effective_start=None, effective_end=None, appointment_fraction=None)


def parse_berkeley(key='berkeley'):
    rows = []
    for card in load_tree(key).all(cls='cc-image-list__item__content'):
        heading = card.first('h3')
        if heading is None or heading.first('a') is None:
            continue
        a = heading.first('a')
        strong = card.first('strong')
        if strong is None:
            raise ValueError('Berkeley card missing role')
        url = urllib.parse.urljoin(URLS[key], a.attrs['href'])
        rows.append(person('berkeley', a.text(), strong.text(), url, key,
                           'h3 a[href="' + a.attrs['href'] + '"]; first strong'))
    return rows


def parse_illinois(key):
    rows = []
    for card in load_tree(key).all(cls='person'):
        name, title = card.first(cls='name'), card.first(cls='title')
        if name is None or name.first('a') is None or title is None:
            raise ValueError('Illinois person card missing name/profile/title')
        a = name.first('a')
        row = person('illinois', a.text(), title.text(),
                     urllib.parse.urljoin(URLS[key], a.attrs['href']), key, '#' + card.attrs['id'])
        row['source_category_codes'] = [c for c in card.attrs.get('class', '').split() if c.startswith('cat')]
        rows.append(row)
    return rows


def parse_stanford(key):
    rows = []
    for card in load_tree(key).all(cls='orglist__row'):
        h, title = card.first(cls='orglist__display-name'), card.first(cls='orglist__person-title')
        if h is None or title is None or h.first('a') is None:
            raise ValueError('Stanford faculty card missing fields')
        a = h.first('a')
        rows.append(person('stanford', a.text(), title.text(), a.attrs['href'], key,
                           'h3 a[href="' + a.attrs['href'] + '"]'))
    return rows


def parse_texas(key):
    rows = []
    for card in load_tree(key).all(cls='facentry'):
        h, title = card.first('h4'), card.first(cls='facpos')
        if h is None or title is None or h.first('a') is None:
            raise ValueError('Texas faculty card missing fields')
        a = h.first('a')
        rows.append(person('texas', a.text(), title.text(),
                           urllib.parse.urljoin(URLS[key], a.attrs['href']), key,
                           'h4 a[href="' + a.attrs['href'] + '"]'))
    return rows


def parse_gatech(key):
    rows = []
    for card in load_tree(key).all(cls='directory-person'):
        n = card.first(cls='field--name-field-person-name')
        title = card.first(cls='field--name-field-person-official-job-title')
        a = card.first(cls='directory-person-wrapper-link')
        if n is None or title is None or a is None:
            raise ValueError('Georgia Tech faculty card missing fields')
        adjunct = card.first(cls='field--name-field-person-ece-adjuncts')
        r = person('gatech', n.text(), title.text(),
                   urllib.parse.urljoin(URLS[key], a.attrs['href']), key,
                   'a[href="' + a.attrs['href'] + '"]')
        if adjunct and adjunct.text():
            r.update(category='affiliate', included=False, decision_basis='Official directory marks ECE adjunct')
        rows.append(r)
    return rows


def pagination_last(key):
    pages = []
    for a in load_tree(key).all('a'):
        values = urllib.parse.parse_qs(urllib.parse.urlsplit(a.attrs.get('href', '')).query)
        if 'page' in values and values['page'][0].isdigit():
            pages.append(int(values['page'][0]))
    return max(pages, default=0)


def collect(refresh=False):
    sources = [fetch(k, u, refresh) for k, u in URLS.items() if not re.search(r'_p\d+$', k)]
    extra_rows = []
    for school, parser in [('stanford', parse_stanford), ('gatech', parse_gatech)]:
        last = pagination_last(school)
        if last > 20:
            raise ValueError('Unexpected pagination; inspect before expanding collection')
        for page in range(1, last + 1):
            key = f'{school}_p{page}'
            URLS[key] = URLS[school] + ('&' if '?' in URLS[school] else '?') + f'page={page}'
            sources.append(fetch(key, URLS[key], refresh))
            extra_rows.extend(parser(key))
    by_source = {s['key']: s for s in sources}
    rows = parse_berkeley() + parse_illinois('illinois') + parse_stanford('stanford') + parse_texas('texas') + parse_gatech('gatech') + extra_rows
    for school in SCHOOLS:
        if not any(r['school']==school for r in rows):
            raise ValueError('No parsed roster entries; inspect extraction before continuing: '+school)
    # Membership in the ECE department list distinguishes regular ECE roles from
    # affiliates whose displayed title belongs to a different department.
    dept = {r['profile_url']: r for r in parse_illinois('illinois_dept')}
    texas_dept = {r['profile_url'] for r in parse_texas('texas_ece')}
    for r in rows:
        if r['school'] == 'illinois':
            r['department_roster_member'] = r['profile_url'] in dept
            if r['profile_url'] not in dept and r['category'] in ('regular', 'uncertain'):
                r.update(category='affiliate', included=False,
                         decision_basis='Listed in all-faculty directory but absent from Department Faculty list')
            if r['profile_url'] in dept:
                r['corroborating_source_keys'] = ['illinois_dept']
                authoritative = dept[r['profile_url']]
                r['all_directory_title'] = r['original_title']
                r['original_title'] = authoritative['original_title']
                r['source_key'] = 'illinois_dept'
                r['source_locator'] = authoritative['source_locator']
                r['category'] = classify(r['original_title'])
                r['included'] = r['category'] == 'regular'
                if r['original_title'] == 'Department Head, Electrical & Computer Engineering':
                    r.update(category='regular', included=True,
                             decision_basis='Department Faculty membership; academic department head, rank to corroborate on profile')
        if r['school'] == 'texas':
            r['department_roster_member'] = r['profile_url'] in texas_dept
            if r['profile_url'] not in texas_dept and r['category'] == 'regular':
                r.update(category='affiliate', included=False,
                         decision_basis='All-faculty listing; absent from ECE Faculty category')
            elif r['profile_url'] in texas_dept:
                r['corroborating_source_keys'] = ['texas_ece']
    summaries = []
    for school, (oid, name, unit) in SCHOOLS.items():
        selected = [r for r in rows if r['school'] == school]
        summaries.append(dict(school=school, name=name, institution_id='https://openalex.org/' + oid,
                              unit=unit, roster_entries=len(selected), categories=dict(Counter(r['category'] for r in selected)),
                              regular_count=sum(r['included'] for r in selected) if selected else None,
                              roster_status='source_enumerated_not_independent_census' if selected else 'blocked',
                              publishable_headcount=None,
                              independent_census_reconciled=False,
                              source_keys=[k for k in URLS if k.startswith(school)],
                              observation_note='Retrieval time is not an effective appointment or census date.'))
    for r in rows:
        r['observed_at'] = by_source[r['source_key']]['fetched_at']
    overrides_path = OUT / 'roster-review-overrides.json'
    if overrides_path.exists():
        overrides = {r['person_id']:r for r in json.loads(overrides_path.read_text())}
        for r in rows:
            if r['person_id'] in overrides:
                o = overrides[r['person_id']]
                r['directory_category'] = r['category']
                r.update(category=o['category'], included=o['category']=='regular',
                         decision_basis=o['reason'], decision_evidence_source_keys=o['source_keys'])
                if 'verified_title' in o: r['verified_title'] = o['verified_title']
        for s in summaries:
            selected = [r for r in rows if r['school']==s['school']]
            s['categories'] = dict(Counter(r['category'] for r in selected))
            s['regular_count'] = sum(r['included'] for r in selected)
    write_json(OUT / 'sources.json', sources)
    write_json(OUT / 'roster.json', rows)
    write_json(OUT / 'schools.json', summaries)
    with (OUT / 'roster.csv').open('w', newline='') as f:
        fields = ['person_id', 'school', 'name', 'original_title', 'category', 'included', 'profile_url', 'source_key', 'source_locator', 'observed_at', 'decision_basis']
        w = csv.DictWriter(f, fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    print(json.dumps(summaries, indent=2))


def normalize_name(name):
    name = re.sub(r'\([^)]*\)', '', name)
    if ',' in name:
        family, given = name.split(',', 1)
        name = given + ' ' + family
    name = ''.join(c for c in unicodedata.normalize('NFKD', name.casefold()) if not unicodedata.combining(c))
    return re.sub(r'[^\w]+', ' ', name).strip()


def sample():
    rows = json.loads((OUT / 'roster.json').read_text())
    population_path = OUT / 'sampling-population.json'
    if not population_path.exists():
        write_json(population_path, [dict(person_id=r['person_id'], school=r['school'], name=r['name']) for r in rows if r['included']])
    population = json.loads(population_path.read_text())
    picks = []
    for school in SCHOOLS:
        eligible = [r for r in population if r['school'] == school]
        eligible.sort(key=lambda r: sha((SEED + r['person_id']).encode()))
        for r in eligible[:3]:
            picks.append({'person_id': r['person_id'], 'school': school, 'name': r['name'],
                          'stratum': 'roster_hash_sample', 'seed': SEED})
    write_json(OUT / 'roster-sample.json', picks)
    print(json.dumps(picks, ensure_ascii=False, indent=2))


def name_key(name):
    return ' '.join(t for t in normalize_name(name).split() if len(t) > 1)


def doi_key(value):
    value = urllib.parse.unquote(value).lower()
    match = re.search(r'10\.\d{4,9}/[^\s<>"?#]+', value)
    return match.group(0).rstrip('.,;)') if match else None


def anchors():
    refs = []
    for filename in ['profile-sources.json', 'review-sources.json']:
        for entry in json.loads((OUT / filename).read_text()):
            source = entry['source']
            if source.get('error'): continue
            for a in load_tree(source['key']).all('a'):
                href = a.attrs.get('href', '')
                doi = doi_key(href)
                if doi:
                    refs.append(dict(person_id=entry['person_id'], name=entry['name'],
                        source_key=source['key'], source_url=source['url'], source_sha256=source['sha256'],
                        doi=doi, locator='a[href="' + href + '"]', anchor_label=a.text()[:300],
                        status='candidate', basis='Publication identifier on university or officially linked personal publication page'))
            for match in re.finditer(r'10\.\d{4,9}/[^\s<>"?#]+', load_tree(source['key']).text(), re.I):
                doi = doi_key(match.group())
                refs.append(dict(person_id=entry['person_id'], name=entry['name'],
                    source_key=source['key'], source_url=source['url'], source_sha256=source['sha256'],
                    doi=doi, locator='text DOI ' + doi, anchor_label='Explicit DOI in publication reference',
                    status='candidate', basis='DOI printed in university-linked publication reference'))
    unique = {(r['person_id'],r['source_key'],r['doi']):r for r in refs}
    write_json(OUT / 'publication-anchors.json', list(unique.values()))
    print(json.dumps(dict(Counter(r['name'] for r in unique.values())), indent=2))


def anchored_papers():
    refs = json.loads((OUT / 'publication-anchors.json').read_text())
    index = defaultdict(list)
    for r in refs: index[r['doi']].append(r)
    people = {p['person_id']:p for p in json.loads((OUT / 'roster.json').read_text())}
    found = {}
    inventory = json.loads((OUT / 'cache-inventory.json').read_text())
    for item in inventory:
        path = ROOT / item['path']; blob = path.read_bytes()
        if sha(blob) != item['sha256']: raise ValueError('Cache changed: ' + item['path'])
        for line_no,line in enumerate(blob.splitlines(), 1):
            w = json.loads(line); doi=doi_key(w.get('doi') or '')
            if doi not in index: continue
            for ref in index[doi]:
                for pos,a in enumerate(w.get('authorships') or []):
                    person_name=normalize_name(people[ref['person_id']]['name']).split()
                    author_name=normalize_name(a.get('author_name') or '').split()
                    if not author_name or not person_name or author_name[-1] != person_name[-1] or author_name[0][0] != person_name[0][0]: continue
                    key = (ref['person_id'], doi, pos)
                    if key in found: continue
                    found[key] = dict(person_id=ref['person_id'], name=ref['name'], doi=doi,
                        title=w.get('title'), work_key='doi:'+doi, year=w.get('publication_year'),
                        byline_position=pos, author_name=a.get('author_name'), author_id=a.get('author_id'),
                        author_count=len(w['authorships']),
                        institution_ids=sorted(i['id'] for i in a.get('institutions',[]) if i.get('id')),
                        cache_path=item['path'], line=line_no, record_sha256=sha(line),
                        evidence_source_key=ref['source_key'], evidence_locator=ref['locator'],
                        status='candidate', basis='Exact publication DOI plus compatible byline name; awaiting reference review')
    write_json(OUT / 'anchored-paper-candidates.json', list(found.values()))
    print(json.dumps(dict(Counter(r['name'] for r in found.values())), indent=2))


def discover():
    """Generate name candidates and independent high-credit controls, not matches."""
    started = time.monotonic()
    people = json.loads((OUT / 'roster.json').read_text())
    names = defaultdict(list)
    for p in people:
        names[name_key(p['name'])].append(p['person_id'])
    insts = {'https://openalex.org/' + v[0]: k for k, v in SCHOOLS.items()}
    candidates, credit = {}, defaultdict(float)
    path = ROOT / 'site/data/author-info.csv'
    with path.open(newline='') as f:
        for row in csv.DictReader(f):
            if not 2016 <= int(row['year']) <= 2025:
                continue
            author = row['author_name']
            amount = float(row['adjusted_count'])
            school = insts.get(row['institution_id'])
            if school:
                credit[(school, row['author_id'], author)] += amount
            for pid in names.get(name_key(author), []):
                key = (pid, row['author_id'], author, row['institution_id'])
                c = candidates.setdefault(key, dict(person_id=pid, author_id=row['author_id'] or None,
                    author_name=author, institution_id=row['institution_id'], years=[], adjusted_count=0,
                    status='candidate', basis='Normalized name only; not accepted identity evidence'))
                if int(row['year']) not in c['years']:
                    c['years'].append(int(row['year']))
                c['adjusted_count'] += amount
    controls, missing_id_groups = [], []
    for school in SCHOOLS:
        entries = [(v, a, n) for (s, a, n), v in credit.items() if s == school]
        entries.sort(key=lambda x: (-x[0], x[1], x[2]))
        missing_id_groups.extend(dict(school=school, author_name=n, adjusted_count=round(v,5),
            issue='Missing author ID: aggregate key can combine unrelated byline authors', status='not_a_verified_person')
            for v,a,n in entries if not a)
        for value, aid, name in [e for e in entries if e[1]][:1]:
            controls.append(dict(school=school, author_id=aid or None, author_name=name,
                                 adjusted_count=round(value, 5), stratum='highest_aggregate_credit_2016_2025',
                                 status='unreviewed', note='Aggregate ID/name group, not a verified person'))
    for c in candidates.values():
        c['years'].sort(); c['adjusted_count'] = round(c['adjusted_count'], 5)
    write_json(OUT / 'name-candidates.json', sorted(candidates.values(), key=lambda c: (c['person_id'], str(c['author_id']), c['institution_id'])))
    write_json(OUT / 'high-credit-sample.json', controls)
    write_json(OUT / 'aggregate-identity-findings.json', missing_id_groups)
    write_json(OUT / 'discovery-run.json', dict(input=str(path.relative_to(ROOT)),
        input_sha256=sha(path.read_bytes()), window=[2016, 2025], candidate_groups=len(candidates),
        people_with_name_candidates=len({x['person_id'] for x in candidates.values()}),
        elapsed_seconds=round(time.monotonic()-started, 3)))
    print(json.dumps(controls, indent=2))


def scan():
    """Draw authorship controls and retrieve paper examples in one cache pass."""
    started = time.monotonic()
    people = {p['person_id']: p for p in json.loads((OUT / 'roster.json').read_text())}
    sampled = json.loads((OUT / 'roster-sample.json').read_text())
    hard_names = {'Kwabena Boahen', 'Alex Dimakis', 'Yuan Cao', 'Jennifer Bernhard', 'Philip Hillmer'}
    wanted = {x['person_id'] for x in sampled} | {pid for pid,p in people.items() if p['name'] in hard_names}
    by_name = defaultdict(list)
    for pid in wanted:
        by_name[name_key(people[pid]['name'])].append(pid)
    insts = {'https://openalex.org/' + v[0]: k for k,v in SCHOOLS.items()}
    examples = defaultdict(list)
    random_slots = {s: [] for s in SCHOOLS}
    special = {'missing_id': [], 'synthetic_id': []}
    inventory, works = [], 0
    registry = json.loads((ROOT / 'data/areas.json').read_text())
    venue_keys = {v['key'] for area in registry['areas'].values() for v in area['venues']}
    def retain(bucket, record, limit):
        key = (record['work_key'], record['byline_position'])
        if any((r['work_key'], r['byline_position']) == key for r in bucket):
            return bucket
        return sorted(bucket + [record], key=lambda r:r['sampling_key'])[:limit]

    for path in sorted((ROOT / 'cache').glob('*/*/works.jsonl')):
        if path.parts[-3] not in venue_keys or not path.parts[-2].isdigit() or not 2016 <= int(path.parts[-2]) <= 2025:
            continue
        blob = path.read_bytes()
        if blob.startswith(b'version https://git-lfs.github.com/spec/v1'):
            raise ValueError('LFS pointer: ' + str(path))
        inventory.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(blob)})
        for lineno, line in enumerate(blob.splitlines(), 1):
            if not line.strip(): continue
            work = json.loads(line); works += 1
            if not 2016 <= int(work.get('publication_year') or 0) <= 2025: continue
            doi = (work.get('doi') or '').lower().removeprefix('https://doi.org/').removeprefix('http://dx.doi.org/')
            wid = ('doi:' + doi) if doi else work.get('id') or ('cache:' + str(path.relative_to(ROOT)) + ':' + str(lineno))
            authors = work.get('authorships') or []
            for position, a in enumerate(authors):
                name = a.get('author_name') or ''
                pids = by_name.get(name_key(name), [])
                ids = {i.get('id') for i in a.get('institutions', [])}
                schools = sorted({insts[i] for i in ids if i in insts})
                if not pids and not schools: continue
                record = dict(work_key=wid, doi=doi or None, title=work.get('title'),
                              year=work['publication_year'], venue=path.parts[-3],
                              cache_path=str(path.relative_to(ROOT)), line=lineno, record_sha256=sha(line),
                              byline_position=position, author_name=name, author_id=a.get('author_id'),
                              author_count=len(authors), institution_ids=sorted(i for i in ids if i),
                              status='unreviewed', sampling_key=sha((SEED + wid + ':' + str(position)).encode()))
                for pid in pids:
                    r = dict(record, person_id=pid)
                    examples[pid] = retain(examples[pid], r, 5)
                for school in schools:
                    random_slots[school] = retain(random_slots[school], dict(record, school=school, stratum='authorship_hash_sample', seed=SEED), 3)
                    aid = a.get('author_id') or ''
                    kind = 'missing_id' if not aid else 'synthetic_id' if not aid.startswith('http') else None
                    if kind:
                        special[kind] = retain(special[kind], dict(record, school=school, stratum=kind), 3)
    write_json(OUT / 'paper-candidates.json', [r for pid in sorted(examples) for r in examples[pid]])
    write_json(OUT / 'authorship-sample.json', [r for s in SCHOOLS for r in random_slots[s]])
    write_json(OUT / 'identifier-stress-sample.json', [r for k in special for r in special[k]])
    write_json(OUT / 'cache-inventory.json', inventory)
    write_json(OUT / 'scan-run.json', dict(works_scanned=works, files=len(inventory), seed=SEED,
        elapsed_seconds=round(time.monotonic()-started,3), window=[2016,2025],
        note='ECE registry membership and years only. Raw-cache sample may include non-research/excluded works; no score computed.'))
    print(json.dumps({'files':len(inventory),'works':works,'paper_candidates':sum(map(len,examples.values())),'elapsed':time.monotonic()-started}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['collect', 'sample', 'discover', 'scan', 'anchors', 'anchored-papers'])
    p.add_argument('--refresh', action='store_true')
    a = p.parse_args()
    if a.action == 'collect':
        collect(a.refresh)
    elif a.action == 'sample':
        sample()
    elif a.action == 'discover':
        discover()
    elif a.action == 'anchors':
        anchors()
    elif a.action == 'anchored-papers':
        anchored_papers()
    else:
        scan()


if __name__ == '__main__':
    main()
