#!/usr/bin/env python3
"""Collect one school's candidate roster; review before replacing accepted data.

Examples: init; observe --school berkeley; accept --review <file>; export.
All commands are local/offline except observe. No ranking data is changed.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import datetime as dt
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from faculty_pilot import ROOT, OUT as PILOT, Tree, compact
from faculty_registry import canonical_url, stable_id, validate_people
from faculty_store import read, digest, atomic_json, put, load_ref, accepted, check_snapshot, lock, source_hash

DEFAULT_ROOT = ROOT/'data/faculty'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def request_key(value):
    """URL plus method/form identity; different POST filters are distinct evidence."""
    if isinstance(value,str):
        if '#request=' in value:return value
        return canonical_url(value)
    spec=value.get('request') or dict(method=value.get('method','GET').upper(),form=value.get('form',{}),**({'referer':value['referer']} if value.get('referer') else {}))
    url=canonical_url(value['url'])
    if spec['method']=='GET' and not spec.get('referer'):return url
    return url+'#request='+digest(json.dumps(spec,sort_keys=True).encode())[:24]


def request_spec(value):
    spec=value.get('request') or dict(method=value.get('method','GET').upper(),form=value.get('form',{}),**({'referer':value['referer']} if value.get('referer') else {}))
    url=canonical_url(value['url'])
    return url if spec['method']=='GET' and not spec.get('referer') else dict(url=url,**spec)


def verify_usc_filters(result):
    """A requested POST filter is not proof the server actually applied it."""
    request=result.get('request',{})
    if request.get('method')!='POST':return
    root=Tree(result['body'].decode('utf-8',errors='replace')).root
    controls={n.attrs.get('name'):n for n in root.all('select')}
    for name,value in request['form'].items():
        control=controls.get(name)
        actual={o.attrs.get('value') for o in control.all('option') if 'selected' in o.attrs} if control else set()
        expected=set(value if isinstance(value,list) else [value])
        if actual!=expected:raise ValueError(f'Faculty filter not applied by source: {name}')
    result['applied_filters']=request['form']


def page_url(url, page):
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    query['page'] = [str(page)]
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))


def list_key(url):
    url,separator,suffix=url.partition('#request=')
    parsed=urllib.parse.urlsplit(canonical_url(url))
    query=urllib.parse.parse_qs(parsed.query,keep_blank_values=True)
    query.pop('page',None)
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(sorted(query.items()),doseq=True)))+(separator+suffix if separator else '')


def entry_key(row):
    """A named directory entry can have no individual profile, or share a site."""
    return row.get('entry_id') or canonical_url(row['profile_url'])


def prior_lists(root, snapshot, settings):
    if snapshot.get('lists'):return snapshot['lists']
    result={}
    for listing in settings['lists']:
        rows={}
        for url,ref in snapshot['evidence'].items():
            if list_key(url)==list_key(request_key(listing)):
                for row in load_ref(root,ref).get('facts',{}).get('directory_entries',[]):
                    rows[entry_key(row)]=row
        if rows:result[listing['id']]=list(rows.values())
    return result


def parse_directory(body, url, adapter, allow_empty=False, options=None):
    if adapter in ('cards','json_list','mit','purdue','ucsd','ucla','michigan',
                   'asu','vt','tamu','cmu','princeton','cornell','columbia','umn','psu','maryland','wisconsin','ncstate','duke','washington','ucsb','ohio-state','ut-dallas','uc-irvine','northeastern','florida','caltech','nyu','penn','ucf','northwestern','harvard','notre-dame','utah','buffalo','yale','rice','boston','michigan-state','iowa-state','boulder','riverside','rutgers','davis','virginia'):
        from faculty_directories import parse
        return parse(body,url,adapter,canonical_url,options)
    tree = Tree(body.decode('utf-8', errors='replace')).root
    selectors = {'berkeley': ('cc-image-list__item__content', 'h3', None),
                 'gatech': ('directory-person', None, None), 'illinois': ('person', None, None),
                 'stanford': ('orglist__row', None, None), 'texas': ('facentry', 'h4', None),
                 'usc': ('faculty-member', None, None)}
    if adapter not in selectors:
        raise ValueError(f'Unsupported directory adapter: {adapter}')
    rows = []
    for card in tree.all(cls=selectors[adapter][0]):
        if adapter == 'berkeley':
            name, title = card.first('h3'), card.first('strong')
            link = name.first('a') if name else None
        elif adapter == 'gatech':
            name = card.first(cls='field--name-field-person-name')
            title = card.first(cls='field--name-field-person-official-job-title')
            link = card.first(cls='directory-person-wrapper-link')
        elif adapter == 'illinois':
            name, title = card.first(cls='name'), card.first(cls='title')
            link = name.first('a') if name else None
        elif adapter == 'stanford':
            name, title = card.first(cls='orglist__display-name'), card.first(cls='orglist__person-title')
            link = name.first('a') if name else None
        elif adapter == 'usc':
            name,title=card.first(cls='resultName'),card.first(cls='faculty-text')
            link=card.parent if card.parent and card.parent.tag=='a' else None
        else:
            name, title = card.first('h4'), card.first(cls='facpos')
            link = name.first('a') if name else None
        if name is None or title is None or link is None or not link.attrs.get('href'):
            raise ValueError('Directory layout changed: missing name, title or profile')
        title_text=compact(' '.join(c.text() if hasattr(c,'tag') else c for c in title.children if c is not name)) if adapter=='usc' else title.text()
        if not title_text and adapter!='usc':raise ValueError('Directory entry missing academic title')
        display_name=link.text() if adapter=='stanford' else name.text()
        rows.append(dict(name=display_name, title=title_text, profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    explicit_empty=allow_empty and adapter=='usc' and any(n.attrs.get('id')=='results' for n in tree.all('div'))
    if not rows and not explicit_empty:
        raise ValueError('No directory entries; failed parsing is not an empty school')
    pages = {0}
    for link in tree.all('a'):
        target = urllib.parse.urlsplit(urllib.parse.urljoin(url, link.attrs.get('href', '')))
        origin = urllib.parse.urlsplit(url)
        if target.netloc != origin.netloc or target.path != origin.path:
            continue
        for value in urllib.parse.parse_qs(target.query).get('page', []):
            if value.isdigit(): pages.add(int(value))
    return rows, max(pages)


def projection(body, url):
    """Retain factual fields and a semantic checksum, not full bios/contact lists."""
    if body.startswith(b'%PDF'):
        return dict(semantic_version=2,semantic_sha256=digest(body), facts={'format': 'pdf', 'text_not_extracted': True})
    if body.lstrip().startswith((b'{', b'[')):
        return dict(semantic_version=2, semantic_sha256=digest(body), facts={'format': 'json', 'text_not_extracted': True})
    tree = Tree(body.decode('utf-8', errors='replace')).root
    main = tree.first('main') or next((n for n in tree.all() if n.attrs.get('id') in ('content', 'main-content')), None) or tree.first('article') or tree.first('body') or tree
    def visible(node):
        if node.tag in ('nav','footer','script','style','form','noscript'): return ''
        return compact(' '.join(visible(c) if hasattr(c, 'tag') else c for c in node.children))
    text = visible(main)
    fields = []
    for node in main.all(cls='field'):
        value = node.text()
        if re.match(r'^(Official Job Title|Job Title\(s\)|ECE Adjunct|Emeritus Years of Service|Academic Appointments)\b', value, re.I):
            fields.append(value[:300])
    for node in main.all('h3'):
        value=node.text()
        if len(value)<250 and re.search(r'professor|lecturer|emerit|adjunct|research engineer|academic professional|affiliate|visiting|below.the.line',value,re.I):
            fields.append(value)
    fields.extend(n.text() for n in main.all(cls='faculty_academic_title'))
    fields.extend(n.text() for n in main.all(cls='seas-people-profile-title'))
    fields.extend(n.text() for n in main.all(cls='profile-titles'))
    fields.extend(n.text() for n in main.all(cls='profile-single-title'))
    fields.extend(n.text() for n in main.all(cls='profile-details-primary-appointment'))
    heading = main.first('h1') or tree.first('h1')
    markers = sorted(set(m.group(0) for m in re.finditer(r'\bincoming(?:\s+(?:in\s+)?(?:Fall|Spring|Summer|Autumn|Winter))?(?:\s+20\d\d)?\b|\b(?:Fall|Spring|Summer|Autumn|Winter)\s+20\d\d\b|\bBelow[ -]the[ -]Line\b|\b(?:adjunct|emeritus|emerita|retired|by courtesy)\b', text, re.I)))
    return dict(semantic_version=2,semantic_sha256=digest(text.encode()), facts=dict(heading=heading.text() if heading else None, role_fields=fields, appointment_markers=markers))


MAX_SOURCE_BYTES=5*1024*1024
HARD_SOURCE_BYTES=16*1024*1024
SOURCE_LIMITS={}  # canonical URL -> byte limit; set per school from list `max_bytes`, never above HARD_SOURCE_BYTES


def get_url(target):
    stamp = now()
    url=target if isinstance(target,str) else target['url']
    limit=min(SOURCE_LIMITS.get(canonical_url(url),MAX_SOURCE_BYTES),HARD_SOURCE_BYTES)
    spec=dict(method='GET',form={}) if isinstance(target,str) else dict(method=target.get('method','GET').upper(),form=target.get('form',{}),**({'referer':target['referer']} if target.get('referer') else {}))
    try:
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError('Faculty sources must use public HTTPS URLs without credentials')
        if spec['method'] not in ('GET','POST'):raise ValueError('Unsupported source request method')
        data=urllib.parse.urlencode(spec['form'],doseq=True).encode() if spec['method']=='POST' else None
        headers={'User-Agent': 'ECERankings faculty roster research (public university sources)'}
        if spec.get('referer'):
            # A page-context Referer is what the university's own page sends to its directory API; same-site https only.
            ref=urllib.parse.urlsplit(spec['referer'])
            site=lambda host:'.'.join((host or '').split('.')[-2:])
            if ref.scheme!='https' or ref.username or ref.password or site(ref.hostname)!=site(parsed.hostname):
                raise ValueError('Referer must be a same-site public HTTPS page')
            headers['Referer']=spec['referer']
        request = urllib.request.Request(url, data=data,method=spec['method'],headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            if urllib.parse.urlsplit(response.url).scheme!='https':raise ValueError('Source redirected away from HTTPS')
            body = response.read(limit+1)
            if len(body)>limit: raise ValueError(f'Source exceeds {limit//(1024*1024)} MiB collection limit')
            return dict(url=url,request=spec, final_url=response.url, status=response.status, observed_at=stamp, body=body)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return dict(url=url,request=spec, status=getattr(exc, 'code', None), observed_at=stamp, error=str(exc))


def record_source(root, result, old=None, directory_rows=None):
    if result.get('error'): return None, None
    body = result['body']
    evidence = dict(url=result['url'], final_url=result.get('final_url',result['url']), observed_at=result['observed_at'],
                    http_status=result.get('status'), response_sha256=digest(body), **projection(body,result['url']))
    if result.get('capture_format')=='browser_dom':
        if result.get('status') is not None or not result.get('capture_tool'):
            raise ValueError('Browser DOM capture must disclose unavailable HTTP status and its tool')
        evidence.update(response_sha256=None,capture_format='browser_dom',capture_sha256=digest(body),capture_tool=result['capture_tool'])
    if result.get('request',{}).get('method')=='POST' or result.get('request',{}).get('referer'):evidence['request']=result['request']
    if result.get('applied_filters'):evidence['facts']['applied_filters']=result['applied_filters']
    if directory_rows is not None:
        evidence['facts']['directory_entries'] = directory_rows
        evidence['semantic_sha256'] = digest(json.dumps(directory_rows,sort_keys=True,ensure_ascii=False).encode())
    ref = put(root,'evidence',evidence)
    sid = stable_id('source',request_key(result)+':'+digest(body))
    source = dict(id=sid,url=result['url'],final_url=result.get('final_url',result['url']),response_sha256=digest(body),
                  observed_at=result['observed_at'],http_status=result.get('status'),kind=old.get('kind','official_department') if old else 'official_department',
                  assertion_origin=old.get('assertion_origin','university') if old else 'university',
                  upstream_source_ids=old.get('upstream_source_ids',[]) if old else [],provenance_independence='not_assumed', evidence=ref)
    if evidence.get('capture_format')=='browser_dom':
        source.update({k:evidence[k] for k in ('response_sha256','capture_format','capture_sha256','capture_tool')})
    if evidence.get('request'):source['request']=evidence['request']
    return source, ref


def critical_urls(person, by_id):
    ids = {s for a in person['appointments'] for s in a['decision']['source_ids']}
    for claim in person['claims']:
        if claim['property'] in ('official_name','directory_title','department_membership','appointment_detail','appointment_state','announced_start'):
            ids.update(claim['source_ids'])
    return {request_key(by_id[s]) for s in ids}


def settings_for(root, school):
    settings=read(root/'schools.json')['schools'][school]
    listings=settings.get('lists',[])
    if settings.get('roster_mode','primary') not in ('primary','union'):
        raise ValueError('Invalid roster mode')
    if sum(x.get('primary') is True for x in listings)!=1 or len({x['id'] for x in listings})!=len(listings):
        raise ValueError('Configure one primary directory and unique list identifiers')
    primary=next(x for x in listings if x.get('primary'))
    if canonical_url(primary['url'])!=canonical_url(settings['roster_url']):raise ValueError('Primary directory and roster URL differ')
    if any(urllib.parse.parse_qs(urllib.parse.urlsplit(x['url']).query).get('page',['0'])!=['0'] for x in listings):
        raise ValueError('Start directory pagination at page zero')
    return settings


def source_origin(url,settings,old):
    if old:return old
    host=urllib.parse.urlsplit(url).hostname or ''
    university='.'.join((urllib.parse.urlsplit(settings['roster_url']).hostname or '').split('.')[-2:])
    personal='/~' in url or host.startswith(('people.','users.'))
    if host==university or host.endswith('.'+university):
        kind='university_hosted_personal' if personal else 'official_department'
    else:kind='university_linked_personal'
    return dict(kind=kind,assertion_origin='researcher' if kind.endswith('personal') else 'university')


def init(root=DEFAULT_ROOT, pilot=PILOT, reimport=False):
    with lock(root):return _init(root,pilot,reimport)


def _init(root, pilot, reimport):
    if (root/'accepted.json').exists():
        if not reimport:return read(root/'accepted.json')
        _,previous=accepted(root)
        if any(s['review']['kind']!='validated_pilot_import' for s in previous.values()):
            raise ValueError('Cannot reimport over a reviewed refresh')
    report = read(root/'validation.json')
    if report['status']!='passed': raise ValueError('A validated registry baseline is required')
    for path, checksum in report['inputs'].items():
        if digest((ROOT/path).read_bytes())!=checksum: raise ValueError(f'Baseline input changed: {path}')
    imported = put(root,'imports',report)
    config = read(root/'schools.json')['schools']
    people = read(root/'people.json')['people']; sources = read(root/'sources.json')['sources']
    old_rows = read(pilot/'roster.json')
    wanted = {s['response_sha256'] for s in sources}
    bodies = {}
    for folder in [ROOT/'.tmp/faculty-pilot', *sorted((ROOT/'.tmp').glob('astra-*'))]:
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix in ('.html','.pdf'):
                checksum = digest(path.read_bytes())
                if checksum in wanted: bodies[checksum] = path
    index = dict(schema_version=1,schools={})
    policy = read(root/'policy.json')
    for summary in read(root/'current.json')['schools']:
        school=summary['school']; settings=config[school]
        group=[p for p in people if any(a['institution_id']==summary['institution_id'] for a in p['appointments'])]
        used={s for p in group for c in p['claims'] for s in c['source_ids']}
        used.update(s for p in group for a in p['appointments'] for s in a['decision']['source_ids'])
        used.update(s for p in group for i in p['identifiers'] for s in i['source_ids'])
        used.update(s for p in group for link in p['publication_links'] for s in link['source_ids'])
        configured={list_key(x['url']) for x in settings['lists']}
        selected=[s for s in sources if s['id'] in used or list_key(s['url']) in configured]
        evidence={}
        for source in selected:
            path=bodies.get(source['response_sha256'])
            if not path: continue
            rows=None
            if canonical_url(source['url']).split('?')[0] in {canonical_url(x['url']).split('?')[0] for x in settings['lists']}:
                try: rows,_=parse_directory(path.read_bytes(),source['url'],settings['adapter'])
                except ValueError: pass
            _,ref=record_source(root,dict(url=source['url'],body=path.read_bytes(),status=200,observed_at=source['observed_at']),source,rows)
            evidence[canonical_url(source['url'])]=ref
        roster=[dict(name=r['name'],title=r['original_title'],profile_url=canonical_url(r['profile_url'])) for r in old_rows if r['school']==school]
        # Original pilot overrides were reviewed separately; keep source card titles.
        for entry in roster:
            original=next(r for r in old_rows if r['school']==school and canonical_url(r['profile_url'])==entry['profile_url'])
            entry['title']=original.get('all_directory_title',original['original_title'])
        snapshot=dict(schema_version=1,school=school,institution_id=summary['institution_id'],name=summary['name'],unit=summary['unit'],
            roster_url=settings['roster_url'],observed_on=summary['observed_on'],observed_at=now(),policy_id=policy['id'],
            policy_sha256=digest((root/'policy.json').read_bytes()),config_sha256=digest(json.dumps(settings,sort_keys=True).encode()),
            parent=None,people=group,sources=selected,evidence=evidence,roster=roster,lists={},failures=[],
            coverage=dict(complete=True,method='Imported enumerated and independently reviewed pilot',entries=len(roster)),
            review=dict(reconciled=True,kind='validated_pilot_import',validation=imported),diff={})
        check_snapshot(root,snapshot,policy,validate_people)
        index['schools'][school]=put(root,f'observations/{school}',snapshot)
    atomic_json(root/'accepted.json',index)
    return index


def observe(root, school, observed_on=None, fetch=get_url, workers=4, audit_transport='configured'):
    if audit_transport not in ('configured','handoff'):raise ValueError('Invalid audit transport')
    observed_on=observed_on or dt.datetime.now(dt.timezone.utc).date().isoformat()
    dt.date.fromisoformat(observed_on)
    if not re.fullmatch('[a-z][a-z0-9-]*',school):raise ValueError('Invalid school identifier')
    settings=settings_for(root,school)
    SOURCE_LIMITS.clear()
    SOURCE_LIMITS.update({canonical_url(x['url']):int(x['max_bytes']) for x in settings['lists'] if x.get('max_bytes')})
    index, baselines=accepted(root)
    baseline=baselines.get(school)
    if settings.get('country')!='US': raise ValueError('Current policy supports US units only')
    policy=read(root/'policy.json')
    old_sources={s['id']:s for s in baseline['sources']} if baseline else {}
    aliases={canonical_url(k):canonical_url(v) for k,v in settings.get('profile_url_aliases',{}).items()}
    old_by_url={request_key(s):s for s in old_sources.values()}
    primary_key=request_key(next(x for x in settings['lists'] if x['primary']))
    results={};evidence={};new_sources={};failures=[];lists={};primary=[]
    def save(result, rows=None):
        url=request_key(result);results[url]=result
        if result.get('error'):
            failures.append({k:v for k,v in result.items() if k!='body'});return
        source,ref=record_source(root,result,source_origin(url,settings,old_by_url.get(url)),rows)
        evidence[url]=ref;new_sources[url]=source
    for listing in settings['lists']:
        all_rows=[]
        try:
            result=fetch(request_spec(listing))
            if result.get('error'):save(result);continue
            if settings['adapter']=='usc':verify_usc_filters(result)
            rows,last=parse_directory(result['body'],result['url'],settings['adapter'],allow_empty=not listing['primary'] and listing.get('allow_empty',False),options=listing.get('cards',settings.get('cards')))
            if settings.get('directory_only'):
                rows=[row if row.get('entry_id') else dict(name=row['name'],title=row['title'],profile_url=canonical_url(result['url']),entry_id=f"{school}:{canonical_url(row['profile_url'])}",profile_kind='official_directory_entry') for row in rows]
            if last>settings.get('max_pages',20): raise ValueError('Pagination exceeds configured safety limit')
            if listing.get('method','GET').upper()=='POST' and last:raise ValueError('POST pagination requires a source-specific paging adapter')
            save(result,rows);all_rows.extend(rows)
            for page in range(1,last+1):
                if settings['adapter'] in ('ucla','duke','harvard','boston'):
                    from faculty_directories import page_url as path_page_url
                    target=path_page_url(listing['url'],page,settings['adapter'])
                else:target=page_url(listing['url'],page+listing.get('page_offset',0))
                if listing.get('referer'):target=dict(url=target,method='GET',form={},referer=listing['referer'])
                result=fetch(target)
                if result.get('error'):save(result);continue
                rows,advertised=parse_directory(result['body'],result['url'],settings['adapter'],options=listing.get('cards',settings.get('cards')))
                if settings.get('directory_only'):
                    rows=[row if row.get('entry_id') else dict(name=row['name'],title=row['title'],profile_url=canonical_url(result['url']),entry_id=f"{school}:{canonical_url(row['profile_url'])}",profile_kind='official_directory_entry') for row in rows]
                if advertised>last: raise ValueError('Pagination changed during collection')
                save(result,rows);all_rows.extend(rows)
            urls=[entry_key(r) for r in all_rows]
            if len(set(urls))!=len(urls): raise ValueError('Duplicate profile across directory pages')
            lists[listing['id']]=all_rows
            if listing['primary']:primary=all_rows
        except (ValueError,KeyError) as exc:
            if 'result' in locals() and not result.get('error') and request_key(result) not in results:
                save(result)
            failures.append(dict(url=listing['url'],request_key=request_key(listing),list_id=listing['id'],error=str(exc),stage='directory_parse'))
    if settings.get('roster_mode')=='union':
        # Some universities publish courtesy and emeritus rosters separately.
        # Preserve every list, but give each profile one candidate identity.
        by_name=settings.get('union_by_name',False)
        import unicodedata
        def name_key(name):
            text=''.join(c for c in unicodedata.normalize('NFKD',name.casefold()) if not unicodedata.combining(c))
            return 'name:'+' '.join(sorted(t for t in re.sub(r'[^\w]+',' ',re.sub(r'\([^)]*\)','',text)).split() if len(t)>1 and t not in ('dr','phd','jr','sr')))
        aliases_by_name={name_key(a):name_key(c) for a,c in settings.get('name_aliases',{}).items()}
        def union_key(row):
            if not by_name:return entry_key(row)
            key=name_key(row['name'])
            return aliases_by_name.get(key,key)
        combined={}
        for r in primary:
            key=union_key(r)
            if key in combined and by_name:
                if r['title'] not in combined[key]['title'].split(' | '):combined[key]['title']+=' | '+r['title']
            else:combined[key]=r
        for listing in settings['lists']:
            if listing.get('crosscheck_only', False):
                continue
            for row in lists.get(listing['id'], []):
                key=union_key(row)
                if key in combined:
                    if by_name and row['title'] not in combined[key]['title'].split(' | '):combined[key]['title']+=' | '+row['title']
                else:combined[key]=row
        for row in settings.get('supplemental_profiles',[]):
            combined.setdefault(entry_key(row),dict(name=row['name'],title=row['title'],profile_url=canonical_url(row['profile_url'])))
        primary=list(combined.values())
    people=copy.deepcopy(baseline['people']) if baseline else []
    previous_profiles={canonical_url(r['profile_url']) for r in baseline['roster']} if baseline else set()
    current_profiles={r['profile_url'] for r in primary}
    def is_retained_past(person):
        appointments=[a for a in person['appointments'] if a['institution_id']==settings['institution_id']]
        absent=not {canonical_url(u) for u in person['profile_urls']} & (previous_profiles|current_profiles)
        return bool(appointments) and absent and all(a['decision']['status']=='excluded' and a['current_state']=='past' for a in appointments)
    policy_changed=bool(baseline and baseline['policy_sha256']!=digest((root/'policy.json').read_bytes()))
    retained_past={p['id'] for p in people if is_retained_past(p) and not policy_changed}
    urls={aliases.get(canonical_url(r['profile_url']),canonical_url(r['profile_url'])) for r in primary}
    if not settings.get('directory_only'):
        urls.update(u for person in people if person['id'] not in retained_past for u in critical_urls(person,old_sources))
    urls.update(canonical_url(u) for u in settings.get('supporting_urls',[]))
    remaining=sorted(urls-results.keys())
    remaining=[request_spec(old_by_url[u]) if u in old_by_url else u for u in remaining]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(fetch,remaining):save(result)
    fetched_dates={r['observed_at'][:10] for r in results.values()}
    if fetched_dates!={observed_on}:
        failures.append(dict(stage='observation_date',error='Requested observation date differs from actual source retrieval dates',requested=observed_on,fetched_dates=sorted(fetched_dates)))
    old_roster={entry_key(r):r for r in baseline['roster']} if baseline else {}
    roster={entry_key(r):r for r in primary}
    list_signatures={list_key(request_key(x)) for x in settings['lists']}
    old_lists=prior_lists(root,baseline,settings) if baseline else {}
    crosschecks=[]
    affected_by_lists=set()
    for listing in settings['lists']:
        if listing['primary']:continue
        old={entry_key(r):r for r in old_lists.get(listing['id'],[])}
        new={entry_key(r):r for r in lists.get(listing['id'],[])}
        if old!=new:
            crosschecks.append(listing['id'])
            affected_by_lists.update(u for u in old.keys()|new.keys() if old.get(u)!=new.get(u))
    def same_source(url):
        result=results.get(url)
        if not result or result.get('error'):return False
        old=old_by_url.get(url)
        if old and source_hash(old)==digest(result['body']):return True
        ref=baseline['evidence'].get(url) if baseline else None
        if not ref:return False
        old_evidence=load_ref(root,ref);new_evidence=load_ref(root,evidence[url])
        return (old_evidence.get('semantic_version',1)==new_evidence.get('semantic_version',1) and
                old_evidence['semantic_sha256']==new_evidence['semantic_sha256'] and old_evidence['facts']==new_evidence['facts'])
    replacements={sid:new_sources[request_key(source)]['id'] for sid,source in old_sources.items() if request_key(source) in new_sources and (same_source(request_key(source)) or list_key(request_key(source)) in list_signatures)}
    all_sources={**old_sources,**{s['id']:s for s in new_sources.values()}}
    changes=[]
    known={canonical_url(u):p for p in people for u in p['profile_urls']}
    known.update({key:p for p in people for key in p.get('directory_entry_ids',[])})
    for url,entry in roster.items():
        if url not in known:
            profile_url=entry['profile_url']
            sid=new_sources.get(aliases.get(profile_url,profile_url),new_sources.get(primary_key))
            pid=stable_id('person',url)
            person=dict(id=pid,legacy_ids=[school+':'+digest(url.encode())[:16]],display_name=entry['name'],names=[entry['name']],profile_urls=[profile_url]+([aliases[profile_url]] if profile_url in aliases and aliases[profile_url]!=profile_url else []),identifiers=[],publication_links=[],conflicts=[],
                appointments=[dict(institution_id=settings['institution_id'],unit=settings['unit'],category='unresolved',membership='unresolved',current_state='unknown',effective_from=None,effective_to=None,observed_on=observed_on,decision=dict(status='unresolved',reason='New person needs appointment review',policy_id=policy['id'],source_ids=[sid['id']] if sid else [],reviewers=[],independently_reviewed=False))],
                claims=[dict(id=stable_id('claim',pid+':name'),property='official_name',value=entry['name'],state='supported',source_ids=[sid['id']] if sid else [],locator='Named directory entry')])
            if entry.get('entry_id'):
                person.update(directory_entry_ids=[entry['entry_id']],profile_kind='official_directory_entry')
            people.append(person);known[url]=person
    for person in people:
        if person['id'] in retained_past:continue
        candidates=person.get('directory_entry_ids',[])+[canonical_url(u) for u in person['profile_urls']]
        url=next((u for u in candidates if u in old_roster or u in roster),candidates[0])
        issues=[]
        if url not in old_roster:issues.append('added')
        elif url not in roster:issues.append('absent_from_directory_requires_departure_evidence')
        elif old_roster[url]!=roster[url]:issues.append('directory_name_or_title_changed')
        if url in affected_by_lists:issues.append('official_category_membership_or_title_changed')
        critical=critical_urls(person,old_sources) if person['id'] in {p['id'] for p in (baseline['people'] if baseline else [])} else set()
        changed=[u for u in critical if list_key(u) not in list_signatures and not same_source(u)]
        if changed:issues.append('appointment_evidence_changed_or_unavailable')
        if baseline and baseline['policy_sha256']!=digest((root/'policy.json').read_bytes()):issues.append('policy_changed')
        if baseline and baseline['config_sha256']!=digest(json.dumps(settings,sort_keys=True).encode()):issues.append('school_configuration_changed')
        for claim in person['claims']:claim['source_ids']=sorted({replacements.get(s,s) for s in claim['source_ids']})
        for identifier in person['identifiers']:identifier['source_ids']=sorted({replacements.get(s,s) for s in identifier['source_ids']})
        for link in person['publication_links']:link['source_ids']=sorted({replacements.get(s,s) for s in link['source_ids']})
        for appointment in person['appointments']:
            decision=appointment['decision'];decision['source_ids']=sorted({replacements.get(s,s) for s in decision['source_ids']})
            appointment['observed_on']=observed_on
            if issues:
                decision.update(status='unresolved',reason='; '.join(issues),policy_id=policy['id'],independently_reviewed=False)
        if issues:changes.append(dict(person_id=person['id'],name=person['display_name'],profile_url=url,reasons=issues,changed_sources=changed,previous=old_roster.get(url),proposed=roster.get(url)))
    # Category-list changes can reveal omissions even when the primary list is stable.
    snapshot=dict(schema_version=1,workflow_version=2,school=school,institution_id=settings['institution_id'],name=settings['name'],unit=settings['unit'],roster_url=settings['roster_url'],
        observed_on=observed_on,observed_at=now(),policy_id=policy['id'],policy_sha256=digest((root/'policy.json').read_bytes()),
        metric_id=policy.get('metric_id','ece_regular_faculty'),count_basis=policy.get('count_basis',''),
        config_sha256=digest(json.dumps(settings,sort_keys=True).encode()),parent=index['schools'].get(school),people=people,sources=list(all_sources.values()),evidence=evidence,
        roster=primary,lists=lists,profile_url_aliases=aliases,failures=failures,coverage=dict(complete=bool(primary) and not failures,entries=len(primary),lists={k:len(v) for k,v in lists.items()}),
        review=dict(reconciled=False,kind='candidate'),diff=dict(changes=changes,crosscheck_changes=crosschecks,unchanged=len(people)-len(changes)))
    ref=put(root,f'observations/{school}',snapshot)
    atomic_json(root/'attempts'/f'{school}.json',dict(observation=ref,observed_at=snapshot['observed_at'],state='blocked' if failures else 'review_required'))
    review_path=root/'pending-reviews'/Path(ref['file']).name
    atomic_json(review_path,dict(schema_version=1,observation=ref,reviewer='',independent_reviewer='',rationale='',crosschecks_reviewed=False,decisions=[]))
    import faculty_audit
    faculty_audit.prepare(root,ref)
    if not failures and audit_transport=='configured':faculty_audit.run(root,ref)
    return ref,snapshot,review_path


def accept_review(root, review_path):
    with lock(root):
        return _accept_review(root,review_path)


def reassess_policy(root, school):
    """Version a policy-only candidate without pretending to retrieve new pages."""
    with lock(root):
        path=root/'attempts'/f'{school}.json'
        attempt=read(path);previous=attempt['observation'];snapshot=copy.deepcopy(load_ref(root,previous))
        policy=read(root/'policy.json')
        if snapshot['policy_sha256']==digest((root/'policy.json').read_bytes()):
            raise ValueError('Candidate already uses the active policy')
        if snapshot['failures'] or not snapshot['coverage']['complete']:
            raise ValueError('Policy reassessment requires a complete source observation')
        settings=settings_for(root,school)
        if snapshot['config_sha256']!=digest(json.dumps(settings,sort_keys=True).encode()):
            raise ValueError('Source configuration changed; recollect explicitly')
        for ref in snapshot['evidence'].values():load_ref(root,ref)
        index,_=accepted(root)
        if index['schools'].get(school)!=snapshot['parent']:raise ValueError('Accepted parent changed; recollect explicitly')
        snapshot.update(policy_id=policy['id'],policy_sha256=digest((root/'policy.json').read_bytes()),
                        metric_id=policy['metric_id'],count_basis=policy['count_basis'],reassessment_of=previous,
                        reassessed_at=now(),observation_method='Policy reassessment of preserved source captures; original source observation timestamps retained',
                        review=dict(reconciled=False,kind='policy_reassessment'))
        if attempt.get('reviewed_observation'):snapshot['prior_review']=attempt['reviewed_observation']
        changes={x['person_id']:x for x in snapshot['diff']['changes']}
        for person in snapshot['people']:
            appointment=next(a for a in person['appointments'] if a['institution_id']==snapshot['institution_id'])
            appointment['decision'].update(status='unresolved',policy_id=policy['id'],independently_reviewed=False,reason='Explicit reassessment required under the amended policy')
            change=changes.setdefault(person['id'],dict(person_id=person['id'],name=person['display_name'],profile_url=person['profile_urls'][0],reasons=[],changed_sources=[],previous=None,proposed=None))
            if 'policy_changed' not in change['reasons']:change['reasons'].append('policy_changed')
        snapshot['diff'].update(changes=list(changes.values()),unchanged=0)
        ref=put(root,f'observations/{school}',snapshot)
        atomic_json(path,dict(observation=ref,observed_at=snapshot['observed_at'],reassessed_at=snapshot['reassessed_at'],state='review_required',kind='policy_reassessment'))
        review_path=root/'pending-reviews'/Path(ref['file']).name
        atomic_json(review_path,dict(schema_version=1,observation=ref,reviewer='',independent_reviewer='',rationale='',crosschecks_reviewed=False,decisions=[]))
        import faculty_audit
        faculty_audit.prepare(root,ref)
        return ref,snapshot,review_path


def _accept_review(root, review_path):
    index,snapshot=prepare_review(root,review_path,require_complete=True)
    school=snapshot['school']
    ref=put(root,f'observations/{school}',snapshot)
    index['schools'][school]=ref;atomic_json(root/'accepted.json',index)
    return ref


def review_draft(root,review_path):
    """Save adjudicated/pending records without changing accepted pointers."""
    with lock(root):
        _,snapshot=prepare_review(root,review_path,require_complete=False)
        ref=put(root,f"observations/{snapshot['school']}",snapshot)
        statuses={status:sum(a['decision']['status']==status for p in snapshot['people'] for a in p['appointments']) for status in ('included','excluded','unresolved')}
        attempt_path=root/'attempts'/f"{snapshot['school']}.json"
        attempt=read(attempt_path)
        attempt.update(reviewed_observation=ref,reviewed_statuses=statuses,state='blocked' if snapshot['failures'] else 'review_required')
        if snapshot['review'].get('audit'):
            attempt['audit']=dict(result=snapshot['review']['audit'],reconciled=snapshot['review']['reconciled'],issues=snapshot['review'].get('audit_issues',[]))
        atomic_json(attempt_path,attempt)
        return ref,statuses


def prepare_review(root,review_path,require_complete):
    review=read(review_path);snapshot=copy.deepcopy(load_ref(root,review['observation']))
    index,_=accepted(root);school=snapshot['school']
    if index['schools'].get(school)!=snapshot['parent']:raise ValueError('Stale review: accepted roster changed since collection')
    settings=read(root/'schools.json')['schools'][school]
    if snapshot['config_sha256']!=digest(json.dumps(settings,sort_keys=True).encode()):raise ValueError('School configuration changed after collection')
    if not review['reviewer'].strip() or not review['rationale'].strip():raise ValueError('Reviewer and rationale are required')
    if require_complete and (snapshot['failures'] or not snapshot['coverage']['complete']):raise ValueError('Failed collection cannot replace accepted data')
    changes={c['person_id']:c for c in snapshot['diff']['changes']}
    if not review['crosschecks_reviewed']:raise ValueError('Reconcile directory/category coverage before acceptance')
    decisions={d['person_id']:d for d in review['decisions']}
    if not set(changes)<=set(decisions) or not set(decisions)<={p['id'] for p in snapshot['people']} or len(decisions)!=len(review['decisions']):raise ValueError('Every changed person requires exactly one explicit decision; additional corrections must identify known people')
    import faculty_audit
    audit_state=faculty_audit.state_path(root,review['observation'])
    allowed=set(changes)
    if audit_state.exists():allowed.update(load_ref(root,read(audit_state)['job'])['scope']['required_person_ids'])
    if set(decisions)-allowed:raise ValueError('Additional corrections require an expanded independent audit; prepare --force --full')
    sources={s['id']:s for s in snapshot['sources']}
    for item in review.get('supplemental_sources',[]):
        source=item['source'];ref=item['evidence'];evidence=load_ref(root,ref)
        if source.get('evidence')!=ref or source_hash(source)!=source_hash(evidence) or request_key(source)!=request_key(evidence):
            raise ValueError('Supplemental source does not match its immutable evidence')
        if source.get('http_status')!=200 or evidence.get('http_status')!=200 or source['observed_at']!=evidence['observed_at'] or source['observed_at'][:10]!=snapshot['observed_on']:
            raise ValueError('Supplemental source must be successfully retrieved on the observation date')
        if not re.fullmatch(r'[0-9a-f]{64}',source.get('response_sha256','')) or urllib.parse.urlsplit(source['url']).scheme!='https':
            raise ValueError('Supplemental source lacks HTTPS/hash provenance')
        if source['id'] in sources:
            if (sources[source['id']]['response_sha256'],request_key(sources[source['id']]))!=(source['response_sha256'],request_key(source)):
                raise ValueError('Conflicting supplemental source identity')
        else:
            sources[source['id']]=source;snapshot['sources'].append(source)
        snapshot['evidence'][request_key(source)]=ref
    fresh_hashes={url:source_hash(load_ref(root,ref)) for url,ref in snapshot['evidence'].items()}
    fresh={sid for sid,source in sources.items() if fresh_hashes.get(request_key(source)) and fresh_hashes.get(request_key(source))==source_hash(source)}
    for person in snapshot['people']:
        decision=decisions.get(person['id'])
        if not decision:continue
        replacement=decision['appointment']
        if replacement['institution_id']!=snapshot['institution_id'] or replacement['observed_on']!=snapshot['observed_on']:
            raise ValueError('Reviewed appointment belongs to another school/observation')
        if not set(replacement['decision']['source_ids']) & fresh:
            raise ValueError('Changed appointment must cite freshly collected evidence')
        if 'absent_from_directory_requires_departure_evidence' in changes.get(person['id'],{}).get('reasons',[]):
            if not any(c['property']=='appointment_end' and c['source_ids'] and set(c['source_ids'])<=fresh and all(sources.get(s,{}).get('kind') in ('official_department','official_university_profile','official_university_announcement') for s in c['source_ids']) for c in decision.get('claims',[])):
                raise ValueError('Directory absence alone cannot establish departure')
        person['appointments']=[replacement if a['institution_id']==snapshot['institution_id'] else a for a in person['appointments']]
        person['claims'].extend(decision.get('claims',[]))
        for key in ('display_name','names','profile_urls','identifiers'):
            if key in decision:person[key]=decision[key]
    snapshot['workflow_version']=2
    snapshot['review']=dict(reconciled=True,kind='explicit_changes' if decisions else 'unchanged_evidence_carry_forward',reviewer=review['reviewer'],
        rationale=review['rationale'],candidate=review['observation'])
    if review.get('independent_review_scope'):snapshot['review']['independent_review_scope']=review['independent_review_scope']
    if review.get('independent_evidence'):snapshot['review']['independent_evidence']=review['independent_evidence']
    if snapshot['failures'] or any(a['decision']['status']=='unresolved' or (a['decision']['status']=='included' and not a['decision']['independently_reviewed']) for p in snapshot['people'] for a in p['appointments']):
        snapshot['review'].update(reconciled=False,kind='reviewed_pending')
    try:
        audit,reviewer,issues=faculty_audit.verify_gate(root,review['observation'],review,snapshot,require_complete=require_complete)
        snapshot['review'].update(audit=audit,independent_reviewer=reviewer,audit_issues=issues)
        if issues:snapshot['review'].update(reconciled=False,kind='reviewed_pending')
    except ValueError as exc:
        if require_complete:raise
        snapshot['review'].update(reconciled=False,kind='reviewed_pending',audit_issues=[str(exc)])
        if audit_state.exists() and read(audit_state).get('result'):
            snapshot['review']['audit']=read(audit_state)['result']
    policy=read(root/'policy.json')
    def validate_draft_people(people,policy,sources):
        return validate_people(people,policy,sources,require_independent=require_complete)
    check_snapshot(root,snapshot,policy,validate_draft_people,require_review=require_complete)
    return index,snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init','observe','reassess-policy','review','accept','export'])
    parser.add_argument('--registry',type=Path,default=DEFAULT_ROOT)
    parser.add_argument('--school');parser.add_argument('--observed-on')
    parser.add_argument('--review',type=Path);parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    parser.add_argument('--audit-transport',choices=['configured','handoff'],default='configured',help='Use handoff for a host-managed independent agent; acceptance still requires its result')
    parser.add_argument('--reimport-baseline',action='store_true',help='Only replace an initial validated pilot import, never a reviewed refresh')
    args=parser.parse_args();root=args.registry.resolve()
    if args.action=='init':
        index=init(root,reimport=args.reimport_baseline);print(f"Accepted baseline: {len(index['schools'])} schools")
    elif args.action=='observe':
        if not args.school:parser.error('observe requires --school')
        ref,snapshot,review=observe(root,args.school,args.observed_on,workers=args.workers,audit_transport=args.audit_transport)
        import faculty_audit
        print(json.dumps(dict(observation=ref,entries=len(snapshot['roster']),changes=len(snapshot['diff']['changes']),failures=len(snapshot['failures']),review=str(review),audit=read(faculty_audit.state_path(root,ref))),indent=2))
    elif args.action=='reassess-policy':
        if not args.school:parser.error('reassess-policy requires --school')
        ref,snapshot,path=reassess_policy(root,args.school)
        print(json.dumps(dict(observation=ref,review=str(path),sources_retrieved=False),indent=2))
    elif args.action=='accept':
        if not args.review:parser.error('accept requires --review')
        print(json.dumps(accept_review(root,args.review),indent=2))
    elif args.action=='review':
        if not args.review:parser.error('review requires --review')
        ref,statuses=review_draft(root,args.review)
        print(json.dumps(dict(reviewed_observation=ref,statuses=statuses,accepted=False),indent=2))
    else:
        if root!=DEFAULT_ROOT.resolve():parser.error('export uses the project registry')
        import faculty_registry
        faculty_registry.build();faculty_registry.export()


if __name__=='__main__':main()
