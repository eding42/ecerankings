#!/usr/bin/env python3
"""Build the US school queue and multi-source faculty records from reviewed evidence.

This enrichment does not write publication caches, ranking data, or scores.
Historical observations are retained; only accepted current counts are exported.
"""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import uuid
import copy
import tempfile

import faculty_store as store

from faculty_pilot import ROOT, OUT as PILOT, SCRATCH, SCHOOLS, sha, write_json, load_tree

REGISTRY = ROOT / 'data/faculty'
POLICY_ID = 'us-ece-current-v3'
OBSERVED_ON = '2026-11-22'


def read(path):
    return json.loads(path.read_text())


def stable_id(kind, value):
    return kind + '_' + uuid.uuid5(uuid.NAMESPACE_URL, 'https://ecerankings.org/faculty/' + value).hex[:20]


def canonical_url(url):
    p = urllib.parse.urlsplit(url)
    # Host aliases are not interchangeable for retrieval (MIT and Purdue are
    # examples). Preserve the published host; reconcile identities explicitly.
    host = p.netloc.lower()
    return urllib.parse.urlunsplit(('https', host, p.path.rstrip('/'), p.query, ''))


def classify_role(title):
    t = title.casefold()
    t = re.sub(r'\b(?:president|dean|chancellor|chair|director)\s+emerit(?:us|a)\b', '', t)
    rules = [
        (r'emerit', 'emeritus'), (r'\brbw\b|retired.but.working|post[ -]tenure', 'retired_working'),
        (r'adjunct|\badj\b', 'adjunct'), (r'visiting|honorary', 'visiting'),
        (r'of (?:the )?practice|of instruction|teaching|lecturer|instructor', 'teaching'),
        (r'academic professional|acad professional', 'academic_professional'),
        (r'research engineer|research scientist|research investigator|postdoc', 'research_staff'),
        (r'research professor|professor.?\s*\(research\)|professor-research|research associate|research assistant|research fellow', 'research_only'),
        (r'courtesy', 'courtesy'),
        (r'(?:below.the.line|affiliate).*\bprofessor\b|\bprofessor\b.*(?:below.the.line|affiliate)', 'affiliate_professor'),
        (r'below.the.line|affiliate', 'affiliate'),
        (r'in residence|in-residence', 'in_residence'),
        (r'professor|\bprof\b', 'regular'),
    ]
    return next((category for pattern, category in rules if re.search(pattern, t)), 'unresolved')


def read_review_sources():
    """Collect response identities without treating copied facts as corroboration."""
    items = []
    for filename in ['sources.json', 'control-sources.json']:
        items.extend(read(PILOT / filename))
    for filename in ['profile-sources.json', 'review-sources.json', 'us-membership-profile-sources.json', 'gatech-membership-profile-sources.json']:
        if (PILOT/filename).exists():
            items.extend(x['source'] for x in read(PILOT/filename))
    items.extend(x['source'] for x in read(PILOT/'publisher-checks.json'))
    for path in sorted(SCRATCH.glob('scope_*.meta.json')):
        items.append(read(path))
    sources = {}
    for meta in items:
        if not meta.get('sha256'):
            continue
        sid = stable_id('source', canonical_url(meta['url']) + ':' + meta['sha256'])
        host = urllib.parse.urlsplit(meta['url']).netloc.lower()
        key = meta.get('key', '')
        if host == 'api.crossref.org':
            kind, origin = 'publisher_metadata', 'publisher deposit via Crossref'
        elif host == 'profiles.stanford.edu':
            kind, origin = 'official_university_profile', 'Stanford University'
        elif not host.endswith('.edu') and not host.endswith('.ethz.ch') and host != 'ethz.ch':
            kind, origin = 'university_linked_personal', 'researcher; linked from university profile'
        elif host.startswith(('people.', 'users.')) or 'cressler.' in host or '/~' in meta['url']:
            kind, origin = 'university_hosted_personal', 'researcher-hosted university page'
        elif 'researchopportunities.' in host:
            kind, origin = 'official_research_group', 'university departmental research portal'
        elif key.startswith('scope_') and '/news/' in meta['url']:
            kind, origin = 'official_university_announcement', 'university'
        else:
            kind, origin = 'official_department', 'university'
        legacy_keys=set(sources.get(sid,{}).get('legacy_keys',[]))
        if key:legacy_keys.add(key)
        sources[sid] = dict(id=sid, url=meta['url'], final_url=meta.get('final_url',meta['url']),http_status=meta.get('status'),
                            response_sha256=meta['sha256'], observed_at=meta['fetched_at'],
                            kind=kind, assertion_origin=origin, upstream_source_ids=[],
                            provenance_independence='not_assumed', legacy_key=key,legacy_keys=sorted(legacy_keys))
    return sources


def incorporate_audit_sources(sources, audit):
    for s in audit.get('sources', []):
        if not s.get('sha256'): continue
        sid=stable_id('source',canonical_url(s['url'])+':'+s['sha256'])
        sources.setdefault(sid,dict(id=sid,url=s['url'],final_url=s['url'],
            response_sha256=s['sha256'],observed_at=s.get('observed_at',s.get('observed_date',OBSERVED_ON)),
            kind='official_department',assertion_origin='university',upstream_source_ids=[],
            provenance_independence='not_assumed',legacy_key=None))
    for r in audit.get('records', []):
        checksum=r.get('profile_sha256') or r.get('profile_source_sha256')
        urls=r.get('source_urls',[])
        profile=next((u for u in urls if 'profiles.stanford.edu/' in u), None)
        if profile is None: profile=next((u for u in urls if '/Faculty/Homepages/' in u), None)
        if not checksum or not profile: continue
        sid=stable_id('source',canonical_url(profile)+':'+checksum)
        sources.setdefault(sid,dict(id=sid,url=profile,final_url=profile,
            response_sha256=checksum,observed_at=OBSERVED_ON,
            kind='official_university_profile' if 'profiles.stanford.edu/' in profile else 'official_department',
            assertion_origin='university',upstream_source_ids=[],provenance_independence='not_assumed',legacy_key=None))


def school_queue(pilot_summaries):
    inst=read(ROOT/'site/data/institutions.json')
    registry=read(ROOT/'data/areas.json')
    areas={k for k,a in registry['areas'].items() if a.get('default_on',True)}
    activity=defaultdict(float)
    with (ROOT/'site/data/inst-area-year.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            if row['area'] in areas and 2016 <= int(row['year']) <= 2025 and inst.get(row['institution_id'],{}).get('country')=='US':
                activity[row['institution_id']]+=float(row['adjusted_count'])
    for summary in pilot_summaries:activity.setdefault(summary['institution_id'],0)
    pilot_order={s['institution_id']:i for i,s in enumerate(pilot_summaries)}
    order=sorted(activity,key=lambda iid:(0,pilot_order[iid]) if iid in pilot_order else (1,-activity[iid],iid))
    old={r['institution_id']:r for r in read(REGISTRY/'school-queue.json')['schools']} if (REGISTRY/'school-queue.json').exists() else {}
    schools=[]
    by_inst={r['institution_id']:r for r in pilot_summaries}
    accepted_index=read(REGISTRY/'accepted.json') if (REGISTRY/'accepted.json').exists() else None
    configured={s['institution_id']:(key,s) for key,s in read(REGISTRY/'schools.json')['schools'].items()} if (REGISTRY/'schools.json').exists() else {}
    for priority,iid in enumerate(order,1):
        current=by_inst.get(iid)
        state=current['state'] if current else old.get(iid,{}).get('state','discovery_pending')
        history=old.get(iid,{}).get('history',[])
        observed=current['observed_on'] if current else dt.datetime.now(dt.timezone.utc).date().isoformat()
        if not history: history=[dict(state='discovery_pending',observed_on=observed,reason='Candidate US institution found in existing ECE publication data; EE/ECE unit not yet established.')]
        policy_id=current.get('target_policy_id',current['policy_id']) if current else old.get(iid,{}).get('policy_id')
        observation_id=current.get('school_observation_sha256') if current else None
        if current and (not history or history[-1]['state']!=state or old.get(iid,{}).get('policy_id')!=policy_id or old.get(iid,{}).get('verified_count')!=current['headcount'] or old.get(iid,{}).get('school_observation_sha256')!=observation_id):
            history=history+[dict(state=state,observed_on=observed,policy_id=policy_id,reason='Broader courtesy coverage requires a new review; prior count retained as historical evidence.' if current.get('previous_count') else 'Validated reviewed official-roster observation.',school_observation_sha256=observation_id)]
        entry=dict(institution_id=iid,name=inst.get(iid,{}).get('name',current['name'] if current else iid),country='US',priority=priority,
                   priority_basis='Five-school pilot first, then 2016-2025 default-area adjusted credit for collection order only',
                   state=state,policy_id=policy_id,school_observation_sha256=observation_id,unit=current['unit'] if current else old.get(iid,{}).get('unit'),
                   verified_count=current['headcount'] if current else old.get(iid,{}).get('verified_count'),
                   observed_on=observed if current else old.get(iid,{}).get('observed_on'),
                   refresh_due_on=str(dt.date.fromisoformat(observed)+dt.timedelta(days=90)) if current else old.get(iid,{}).get('refresh_due_on'),
                   next_action='Recheck official roster and review additions, departures and role changes by refresh date' if state=='verified' else 'Resolve appointment review' if current else old.get(iid,{}).get('next_action','Find official EE/ECE unit and roster; determine whether in scope'),
                   history=history)
        if current and current.get('previous_count'):
            entry.update(previous_count=current['previous_count'],next_action='Enumerate courtesy and joint/secondary EE/ECE appointments; reconcile a fresh independent audit under the active affiliation policy')
        attempt_path=REGISTRY/'attempts'/f"{current['school']}.json" if current else None
        if attempt_path and attempt_path.exists():
            attempt=read(attempt_path)
            accepted_snapshot=store.load_ref(REGISTRY,accepted_index['schools'][current['school']])
            entry['last_collection_attempt']={**attempt,'state':'verified' if accepted_snapshot['review'].get('candidate')==attempt['observation'] else attempt['state']}
            if entry['last_collection_attempt']['state']!='verified' and not current.get('previous_count'):entry['next_action']='Review latest collection attempt; retain the accepted count until reconciliation succeeds'
        elif not current and iid in configured:
            key,settings=configured[iid]
            pending_path=REGISTRY/'attempts'/f'{key}.json'
            if pending_path.exists():
                attempt=read(pending_path)
                candidate=store.load_ref(REGISTRY,attempt['observation'])
                active_policy=read(REGISTRY/'policy.json')
                stale_policy=candidate['policy_sha256']!=sha((REGISTRY/'policy.json').read_bytes())
                entry.update(state='needs_update' if stale_policy else attempt['state'],unit=settings['unit'],policy_id=active_policy['id'],last_collection_attempt=attempt,
                             verified_count=None,next_action='Re-observe and independently review under the broader ECE-affiliated policy; prior audit remains unchanged' if stale_policy else 'Resolve collection failures and ambiguous appointments, then reconcile independent review; public count withheld')
                if history[-1]['state']!=entry['state']:
                    entry['history']=history+[dict(state=entry['state'],observed_on=attempt['observed_at'][:10],reason='New school collection is pending; no accepted count',observation=attempt['observation'])]
        schools.append(entry)
    return dict(schema_version=1,field='ece',country='US',policy_id=read(REGISTRY/'policy.json')['id'],
                candidate_definition='US institutions with nonzero default-area ECE credit, plus pilot schools. Department existence is unverified until discovery.',
                schools=schools)


def build():
    if (REGISTRY/'accepted.json').exists():
        with store.lock(REGISTRY):return build_from_accepted()
    policy=read(REGISTRY/'policy.json')
    if policy['id']!=POLICY_ID:raise ValueError('Builder and counting policy versions differ')
    raw=read(PILOT/'roster.json')
    sources=read_review_sources()
    reviews={}
    for school in SCHOOLS:
        path=REGISTRY/'reviews'/f'{school}.json'
        if path.exists():
            reviews[school]=read(path)
            original = ROOT / reviews[school]['independent_review_file']
            if sha(original.read_bytes()) != reviews[school]['independent_review_sha256']:
                raise ValueError(f'Independent review changed: {school}')
            incorporate_audit_sources(sources, read(original))
            incorporate_audit_sources(sources,reviews[school])
    by_key=defaultdict(list)
    by_url=defaultdict(list)
    for sid,s in sources.items():
        for key in s.get('legacy_keys',[s.get('legacy_key')]):
            if key:by_key[key].append(sid)
        by_url[canonical_url(s['url'])].append(sid)
    ids_path=REGISTRY/'person-ids.json'
    ids=read(ids_path) if ids_path.exists() else {}
    people=[]
    accepted=read(PILOT/'accepted-matches.json')
    recheck=read(PILOT/'current-authorship-recheck.json') if (PILOT/'current-authorship-recheck.json').exists() else None
    publisher_rows={r['doi']:r for r in read(PILOT/'publisher-checks.json')}
    profile_rows=read(PILOT/'profile-sources.json')+read(PILOT/'review-sources.json')
    for row in raw:
        legacy=row['person_id']
        pid=ids.setdefault(legacy,stable_id('person',canonical_url(row['profile_url'])))
        school=row['school'];audit=reviews.get(school,{})
        decision=next((r for r in audit.get('records',[]) if r['person_id']==legacy), None)
        source_ids=list(by_key.get(row['source_key'],[]))
        if decision:
            for url in decision.get('source_urls',[]): source_ids.extend(by_url.get(canonical_url(url),[]))
        source_ids=sorted(set(source_ids))
        claims=[dict(id=stable_id('claim',pid+':name:'+row['name']),property='official_name',
                     value=row['name'],state='supported',source_ids=by_key.get(row['source_key'],[]),locator=row['source_locator'])]
        names=[row['name']]
        profile_urls={row['profile_url']}
        external_ids=[]
        paper_links=[]
        for link in [a for a in accepted if a['person_id']==legacy]:
            if link['author_name'] not in names:names.append(link['author_name'])
            evidence=by_key.get(link['evidence_source_key'],[])
            paper_links.append(dict(doi=link['doi'],byline_position=link['byline_position'],
                                    printed_name=link['author_name'],provider_author_id=link.get('author_id'),
                                    status='accepted_individual_authorship',source_ids=evidence,
                                    publication_institution_ids=link['institution_ids'],review_observed_on=OBSERVED_ON,
                                    review_file=str((PILOT/'accepted-matches.json').relative_to(ROOT)),
                                    current_check_status=next((r['status'] for r in recheck['records'] if r['person_id']==legacy and r['doi']==link['doi']), 'not_rechecked') if recheck else 'not_rechecked'))
            if link.get('author_id','') and link['author_id'].startswith('https://openalex.org/'):
                eid=dict(namespace='openalex',value=link['author_id'],status='supported_on_matched_authorships',source_ids=evidence)
                if eid not in external_ids:external_ids.append(eid)
        for item in profile_rows:
            if item['person_id']==legacy and not item['source'].get('error'):
                profile_urls.add(item['source']['url'])
                source_key=item['source']['key']
                if (SCRATCH/(source_key+'.html')).exists():
                    for anchor in load_tree(source_key).all('a'):
                        url=anchor.attrs.get('href','')
                        match=re.search(r'orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])',url,re.I)
                        if match:
                            eid=dict(namespace='orcid',value='https://orcid.org/'+match.group(1),
                                     status='linked_on_person_profile',source_ids=by_key.get(source_key,[]))
                            if eid not in external_ids:external_ids.append(eid)
        for link in paper_links:
            publisher=publisher_rows.get(link['doi'])
            if not publisher or publisher.get('error'):continue
            author=publisher['authors'][link['byline_position']]
            if author.get('ORCID'):
                sid=by_key.get(publisher['source']['key'],[])
                eid=dict(namespace='orcid',value=author['ORCID'],status='publisher_asserted_on_matched_authorship',source_ids=sid)
                if eid not in external_ids:external_ids.append(eid)
        if decision:
            category=decision['category'];membership=decision['membership'];status=decision['status']
            for i,fact in enumerate(decision.get('facts',[])):
                evidence=sorted({sid for u in fact['source_urls'] for sid in by_url.get(canonical_url(u),[])})
                claims.append(dict(id=stable_id('claim',pid+':fact:'+str(i)+':'+str(fact['value'])),property=fact['property'],
                    value=fact['value'],state=fact.get('state','supported'),source_ids=evidence,
                    locator=fact.get('locator','Named official appointment entry')))
            appointment=dict(institution_id='https://openalex.org/'+SCHOOLS[school][0],unit=SCHOOLS[school][2],
                category=category,membership=membership,current_state=decision.get('appointment_state','past' if category in ['emeritus','retired_working','departed'] else 'current' if status=='included' else 'not_in_core'),
                effective_from=decision.get('effective_from'),effective_to=decision.get('effective_to'),observed_on=OBSERVED_ON,
                decision=dict(status=status,reason=decision['reason'],policy_id=POLICY_ID,
                              source_ids=source_ids,reviewers=decision.get('reviewers',['Codex']),
                              independently_reviewed=audit.get('independent_review_reconciled',False)))
            conflicts=decision.get('conflicts',[])
        else:
            appointment=dict(institution_id='https://openalex.org/'+SCHOOLS[school][0],unit=SCHOOLS[school][2],
                category='unresolved',membership='unresolved',current_state='unknown',effective_from=None,effective_to=None,
                observed_on=OBSERVED_ON,decision=dict(status='unresolved',reason='Official appointment review pending',policy_id=POLICY_ID,source_ids=source_ids,reviewers=[],independently_reviewed=False))
            conflicts=[]
        people.append(dict(id=pid,legacy_ids=[legacy],display_name=row['name'],names=names,
                           profile_urls=sorted(profile_urls),identifiers=external_ids,appointments=[appointment],
                           claims=claims,publication_links=paper_links,conflicts=conflicts))
    summaries=[]
    for school,(oid,name,unit) in SCHOOLS.items():
        group=[p for p in people if p['appointments'][0]['institution_id']=='https://openalex.org/'+oid]
        states=Counter(p['appointments'][0]['decision']['status'] for p in group)
        incoming=sum(p['appointments'][0]['decision']['status']=='included' and p['appointments'][0]['current_state']=='incoming' for p in group)
        audit=reviews.get(school,{})
        ready=bool(group) and states['unresolved']==0 and audit.get('enumeration_complete') is True and audit.get('independent_review_reconciled') is True
        summaries.append(dict(school=school,institution_id='https://openalex.org/'+oid,name=name,unit=unit,
                              state='verified' if ready else 'review_required',
                              headcount=states['included'] if ready else None,
                              incoming_headcount=incoming if ready else None,current_headcount=states['included']-incoming if ready else None,
                              included_candidates=states['included'],excluded=states['excluded'],unresolved=states['unresolved'],
                              reviewed_entries=len(group),observed_on=OBSERVED_ON,policy_id=POLICY_ID,
                              roster_url=audit.get('roster_url'),source_urls=audit.get('source_urls',[]),
                              count_basis='Official university regular and in-residence EE/ECE faculty, including announced incoming appointments; headcount, not FTE.'))
    write_json(ids_path,ids)
    write_json(REGISTRY/'sources.json',dict(schema_version=1,sources=list(sources.values())))
    write_json(REGISTRY/'people.json',dict(schema_version=1,policy_id=POLICY_ID,people=people))
    write_json(REGISTRY/'school-queue.json',school_queue(summaries))
    snapshot=dict(schema_version=1,policy_id=POLICY_ID,observed_on=OBSERVED_ON,schools=summaries,
                  policy_sha256=sha((REGISTRY/'policy.json').read_bytes()),
                  people_sha256=sha((REGISTRY/'people.json').read_bytes()),
                  sources_sha256=sha((REGISTRY/'sources.json').read_bytes()),
                  decision_digest=sha(json.dumps(reviews,sort_keys=True,ensure_ascii=False).encode()))
    oid=stable_id('observation',json.dumps(snapshot,sort_keys=True,ensure_ascii=False))
    snapshot['id']=oid
    path=REGISTRY/'observations'/f'{OBSERVED_ON}-{oid}.json'
    if path.exists() and read(path)!=snapshot: raise ValueError('Refusing to overwrite immutable observation')
    write_json(path,snapshot)
    write_json(REGISTRY/'current.json',dict(schema_version=1,observation_id=oid,observation_file=str(path.relative_to(REGISTRY)),schools=summaries))
    print(json.dumps([dict(school=s['school'],state=s['state'],headcount=s['headcount'],unresolved=s['unresolved']) for s in summaries],indent=2))


def accepted_components():
    index,snapshots=store.accepted(REGISTRY)
    policy=read(REGISTRY/'policy.json')
    people={};sources={};summaries=[];policies={policy['id']:policy}
    institutions=read(ROOT/'site/data/institutions.json')
    for school,snapshot in snapshots.items():
        if school!=snapshot['school']:raise ValueError('School pointer/observation mismatch')
        if institutions.get(snapshot['institution_id'],{}).get('country')!='US':raise ValueError('Accepted school must match a known US institution')
        pinned_policy=store.observation_policy(REGISTRY,snapshot,allow_historical=True)
        policies[pinned_policy['id']]=pinned_policy
        summary=store.check_snapshot(REGISTRY,snapshot,pinned_policy,validate_people,allow_historical_policy=True)
        if snapshot['policy_sha256']!=sha((REGISTRY/'policy.json').read_bytes()):
            summary['previous_count']={k:summary[k] for k in ('headcount','current_headcount','incoming_headcount','policy_id','metric_id','observed_on')}
            summary.update(state='needs_update',headcount=None,current_headcount=None,incoming_headcount=None,target_policy_id=policy['id'])
        summary['school_observation_sha256']=index['schools'][school]['sha256']
        summaries.append(summary)
        sources.update({s['id']:s for s in snapshot['sources']})
        for person in snapshot['people']:
            if person['id'] not in people:
                people[person['id']]=copy.deepcopy(person)
                continue
            target=people[person['id']]
            for key in ['legacy_ids','names','profile_urls','identifiers','appointments','claims','publication_links','conflicts']:
                for value in person[key]:
                    if value not in target[key]:target[key].append(value)
    errors=validate_people(list(people.values()),policy,sources,historical_policies=policies)
    if errors:raise ValueError('\n'.join(errors))
    return index,list(people.values()),list(sources.values()),summaries


def build_from_accepted():
    index,people,sources,summaries=accepted_components()
    policy=read(REGISTRY/'policy.json');ids=read(REGISTRY/'person-ids.json')
    for person in people:
        for legacy in person['legacy_ids']:
            if legacy in ids and ids[legacy]!=person['id']:raise ValueError('Assigned identity changed without explicit reconciliation')
            ids[legacy]=person['id']
    store.atomic_json(REGISTRY/'person-ids.json',ids)
    decision_policy_ids=sorted({a['decision']['policy_id'] for p in people for a in p['appointments']})
    store.atomic_json(REGISTRY/'people.json',dict(schema_version=1,policy_id=policy['id'],decision_policy_ids=decision_policy_ids,people=people))
    store.atomic_json(REGISTRY/'sources.json',dict(schema_version=1,sources=sources))
    store.atomic_json(REGISTRY/'school-queue.json',school_queue(summaries))
    snapshot=dict(schema_version=1,policy_id=policy['id'],observed_on=max(s['observed_on'] for s in summaries),schools=summaries,
        accepted_index_sha256=sha((REGISTRY/'accepted.json').read_bytes()),
        policy_sha256=sha((REGISTRY/'policy.json').read_bytes()),people_sha256=sha((REGISTRY/'people.json').read_bytes()),sources_sha256=sha((REGISTRY/'sources.json').read_bytes()))
    ref=store.put(REGISTRY,'observations/registry',snapshot)
    store.atomic_json(REGISTRY/'current.json',dict(schema_version=1,observation_id=ref['sha256'],observation_file=ref['file'],schools=summaries))
    print(f'Built registry from {len(summaries)} accepted school observations.')


def validate_people(people, policy, sources, require_independent=True, historical_policies=None):
    """Reject unsupported inclusions without mistaking an excluded person for absence."""
    errors=[]
    ids=[p['id'] for p in people]
    if len(ids)!=len(set(ids)):errors.append('Duplicate local person identity; review merge explicitly')
    byline_keys=set()
    for person in people:
        label=person['display_name']
        for claim in person['claims']:
            if claim['state'] not in policy['claim_states']:errors.append(f'{label}: invalid claim state')
            if not claim['source_ids'] or set(claim['source_ids'])-sources.keys():
                errors.append(f'{label}: claim lacks valid evidence')
        for appointment in person['appointments']:
            d=appointment['decision']
            appointment_policy=(historical_policies or {}).get(d['policy_id'],policy)
            if appointment['category'] not in appointment_policy['included_categories']+appointment_policy['excluded_categories']+['unresolved']:
                errors.append(f'{label}: invalid appointment category')
            if d['policy_id']!=appointment_policy['id'] or d['status'] not in appointment_policy['decision_values']:
                errors.append(f'{label}: invalid decision policy/status')
            if appointment['membership'] not in policy['membership_values']:
                errors.append(f'{label}: invalid membership')
            if not d['source_ids'] or set(d['source_ids'])-sources.keys():errors.append(f'{label}: unsupported decision')
            if d['status']=='included':
                if appointment['category'] not in appointment_policy['included_categories'] or appointment['membership']!='ece' or appointment['current_state'] not in appointment_policy['included_appointment_states']:
                    errors.append(f'{label}: ineligible appointment included')
                membership=[c for c in person['claims'] if c['property']=='department_membership']
                if not any(sources.get(s,{}).get('kind') in ('official_department','official_university_profile') for c in membership for s in c['source_ids']):
                    errors.append(f'{label}: no official EE/ECE membership evidence')
                if require_independent and not d['independently_reviewed']:errors.append(f'{label}: inclusion lacks reconciled independent review')
                if appointment['current_state']=='incoming':
                    incoming_claims=[c for c in person['claims'] if c['property']=='appointment_state' and c['value']=='incoming' and c['state'] in ('supported','corroborated')]
                    if not any(sources.get(s,{}).get('kind') in ('official_department','official_university_profile','official_university_announcement') for c in incoming_claims for s in c['source_ids']):
                        errors.append(f'{label}: incoming appointment lacks official announcement evidence')
            elif d['status']=='excluded' and appointment['category'] in appointment_policy['included_categories'] and appointment['membership']=='ece':
                errors.append(f'{label}: qualifying appointment excluded inconsistently with policy')
        for identifier in person['identifiers']:
            if not identifier['source_ids'] or set(identifier['source_ids'])-sources.keys():errors.append(f'{label}: unsupported identifier')
        for link in person['publication_links']:
            key=(link['doi'],link['byline_position'])
            if key in byline_keys:errors.append(f'Duplicate accepted authorship: {key}')
            byline_keys.add(key)
            if not link['source_ids'] or set(link['source_ids'])-sources.keys():errors.append(f'{label}: unsupported authorship link')
    return errors


def validation_inputs():
    paths=[REGISTRY/name for name in ['policy.json','person-ids.json','people.json','sources.json','current.json','school-queue.json','discovery-leads.json']]
    if (REGISTRY/'accepted.json').exists():
        paths.extend([REGISTRY/'accepted.json',REGISTRY/'schools.json'])
        paths.extend(sorted((REGISTRY/'policies').glob('*.json')))
        index,snapshots=store.accepted(REGISTRY)
        for school,snapshot in snapshots.items():
            paths.append(REGISTRY/index['schools'][school]['file'])
            paths.extend(REGISTRY/name for name in store.dependencies(REGISTRY,snapshot))
        return {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(set(paths))}
    paths+=sorted((REGISTRY/'reviews').glob('*.json'))
    paths+=sorted((REGISTRY/'policies').glob('*.json'))
    paths+=sorted((REGISTRY/'review-history').glob('*/*.json'))
    paths.extend(PILOT/name for name in ['accepted-matches.json','publication-anchors.json','publisher-checks.json','current-authorship-recheck.json'])
    for path in sorted((REGISTRY/'reviews').glob('*.json')):
        review=read(path)
        paths.append(ROOT/review['independent_review_file'])
        paths.extend(ROOT/r['file'] for r in review.get('supplemental_reviews',[]))
    return {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}


def validate():
    if (REGISTRY/'accepted.json').exists():return validate_accepted_registry()
    policy=read(REGISTRY/'policy.json')
    people=read(REGISTRY/'people.json')['people']
    sources_list=read(REGISTRY/'sources.json')['sources']
    sources={s['id']:s for s in sources_list}
    errors=validate_people(people,policy,sources)
    if len(sources)!=len(sources_list):errors.append('Duplicate source ID')
    for source in sources_list:
        if not re.fullmatch('[0-9a-f]{64}',source['response_sha256']):errors.append('Invalid response checksum')
        if source['kind'] not in policy['source_types']:errors.append('Invalid source type')
    current=read(REGISTRY/'current.json')
    snapshot=read(REGISTRY/current['observation_file'])
    reviews={s:read(REGISTRY/'reviews'/f'{s}.json') for s in SCHOOLS}
    if snapshot['schools']!=current['schools'] or snapshot['id']!=current['observation_id']:
        errors.append('Current pointer differs from immutable observation')
    for name in ['policy','people','sources']:
        if snapshot.get(name+'_sha256')!=sha((REGISTRY/(name+'.json')).read_bytes()):
            errors.append(f'{name} changed since current observation; rebuild')
    if snapshot['decision_digest']!=sha(json.dumps(reviews,sort_keys=True,ensure_ascii=False).encode()):
        errors.append('Current observation predates review changes; rebuild')
    raw=read(PILOT/'roster.json')
    identities=read(REGISTRY/'person-ids.json')
    if any(identities.get(legacy)!=p['id'] for p in people for legacy in p['legacy_ids']):
        errors.append('Assigned person identities differ from the retained ID map')
    for school,review in reviews.items():
        if review['policy_id']!=policy['id']:errors.append(f'{school}: review uses a different counting policy')
        original=ROOT/review['independent_review_file']
        if sha(original.read_bytes())!=review['independent_review_sha256']:errors.append(f'{school}: independent audit changed')
        for extra in review.get('supplemental_reviews',[]):
            if sha((ROOT/extra['file']).read_bytes())!=extra['sha256']:errors.append(f'{school}: supplemental audit changed')
        expected={r['person_id'] for r in raw if r['school']==school}
        decisions={r['person_id']:r for r in review['records']}
        if set(decisions)!=expected or len(decisions)!=len(review['records']):errors.append(f'{school}: roster review coverage incomplete')
        if {r['person_id'] for r in read(original)['records']}!=expected:errors.append(f'{school}: independent review coverage incomplete')
        group=[p for p in people if p['legacy_ids'][0] in expected]
        summary=next(s for s in current['schools'] if s['school']==school)
        counts=Counter(p['appointments'][0]['decision']['status'] for p in group)
        if len(group)!=len(expected) or summary['reviewed_entries']!=len(group):errors.append(f'{school}: extracted population changed')
        ready=review['enumeration_complete'] and review['independent_review_reconciled'] and not counts['unresolved']
        if summary['headcount']!=(counts['included'] if ready else None):errors.append(f'{school}: public count gate failed')
        incoming=sum(p['appointments'][0]['decision']['status']=='included' and p['appointments'][0]['current_state']=='incoming' for p in group)
        if summary['incoming_headcount']!=(incoming if ready else None) or summary['current_headcount']!=(counts['included']-incoming if ready else None):
            errors.append(f'{school}: current/incoming count breakdown differs')
        if (summary['state']=='verified')!=bool(ready):errors.append(f'{school}: count/state disagreement')
        for p in group:
            d=decisions[p['legacy_ids'][0]];a=p['appointments'][0]
            if (a['category'],a['membership'],a['decision']['status'])!=(d['category'],d['membership'],d['status']):errors.append(f'{school}: generated decision differs from review')
            if d.get('appointment_state') and a['current_state']!=d['appointment_state']:errors.append(f'{school}: appointment timing differs from review')
    queue=read(REGISTRY/'school-queue.json')['schools']
    if len({s['institution_id'] for s in queue})!=len(queue):errors.append('Duplicate school queue entry')
    for school in queue:
        if school['country']!='US' or school['state'] not in policy['school_states']:errors.append('Invalid school queue scope/state')
        if not school['history'] or school['history'][-1]['state']!=school['state']:errors.append('Queue state/history mismatch')
    if errors:raise ValueError('\n'.join(errors))
    report=dict(schema_version=1,status='passed',policy_id=policy['id'],observation_id=current['observation_id'],
                people=len(people),candidate_institutions=len(queue),verified_schools=sum(s['state']=='verified' for s in current['schools']),
                accepted_authorship_links=sum(len(p['publication_links']) for p in people),inputs=validation_inputs())
    write_json(REGISTRY/'validation.json',report)
    # A compact factual review table; detailed claims remain in people.json.
    with (REGISTRY/'roster-review.csv').open('w',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['school','person_id','name','category','membership','appointment_state','effective_from','decision','reason','official_profile','observed_on','retained_conflicts'])
        for p in people:
            a=p['appointments'][0]
            writer.writerow([p['legacy_ids'][0].split(':')[0],p['id'],p['display_name'],a['category'],a['membership'],a['current_state'],json.dumps(a['effective_from'],ensure_ascii=False) if a['effective_from'] else '',a['decision']['status'],a['decision']['reason'],p['profile_urls'][0],a['observed_on'],' | '.join(p['conflicts'])])
    print(f"Validated {len(people)} person records, {report['verified_schools']} current school counts and {len(queue)} queued institutions.")
    return report


def validate_accepted_registry():
    index,people,sources,summaries=accepted_components()
    current=read(REGISTRY/'current.json');snapshot=read(REGISTRY/current['observation_file'])
    if sha((REGISTRY/current['observation_file']).read_bytes())!=current['observation_id']:raise ValueError('Current registry observation checksum differs')
    if snapshot.get('accepted_index_sha256')!=sha((REGISTRY/'accepted.json').read_bytes()):raise ValueError('Accepted roster changed; rebuild before exporting')
    if current['schools']!=summaries or snapshot['schools']!=summaries:raise ValueError('Derived school counts differ from accepted observations')
    if read(REGISTRY/'people.json')['people']!=people or read(REGISTRY/'sources.json')['sources']!=sources:raise ValueError('Derived people/sources differ from accepted observations')
    if read(REGISTRY/'people.json').get('decision_policy_ids')!=sorted({a['decision']['policy_id'] for p in people for a in p['appointments']}):raise ValueError('Decision policy inventory differs from accepted observations')
    for name in ['policy','people','sources']:
        if snapshot[name+'_sha256']!=sha((REGISTRY/(name+'.json')).read_bytes()):raise ValueError(f'{name} changed; rebuild before exporting')
    identities=read(REGISTRY/'person-ids.json')
    if any(identities.get(legacy)!=p['id'] for p in people for legacy in p['legacy_ids']):raise ValueError('Retained identity map differs')
    queue=read(REGISTRY/'school-queue.json')['schools']
    for summary in summaries:
        row=next(s for s in queue if s['institution_id']==summary['institution_id'])
        if row['verified_count']!=summary['headcount'] or row['school_observation_sha256']!=summary['school_observation_sha256']:raise ValueError('School queue differs from accepted observation')
    report=dict(schema_version=1,status='passed',policy_id=read(REGISTRY/'policy.json')['id'],observation_id=current['observation_id'],
        people=len(people),candidate_institutions=len(queue),verified_schools=sum(s['state']=='verified' for s in summaries),
        historical_school_observations=sum(s['state']=='needs_update' for s in summaries),accepted_authorship_links=sum(len(p['publication_links']) for p in people),inputs=validation_inputs())
    store.atomic_json(REGISTRY/'validation.json',report)
    with (REGISTRY/'roster-review.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['school','person_id','name','category','membership','appointment_state','effective_from','decision','reason','official_profile','observed_on','retained_conflicts'])
        school_by_inst={s['institution_id']:s['school'] for s in summaries}
        for person in people:
            for appointment in person['appointments']:
                writer.writerow([school_by_inst[appointment['institution_id']],person['id'],person['display_name'],appointment['category'],appointment['membership'],appointment['current_state'],json.dumps(appointment['effective_from'],ensure_ascii=False) if appointment['effective_from'] else '',appointment['decision']['status'],appointment['decision']['reason'],person['profile_urls'][0],appointment['observed_on'],' | '.join(person['conflicts'])])
    print(f"Validated {report['verified_schools']} active-policy school counts, {report['historical_school_observations']} historical school observations and {len(people)} people.")
    return report


def export():
    with store.lock(REGISTRY):return export_locked()


def public_roster_link(configured,summary):
    """The link readers click: a configured human-facing page when the collected source is a data endpoint."""
    url=configured.get(summary.get('school'),{}).get('public_roster_url')
    if not url:return {}
    if urllib.parse.urlsplit(url).scheme!='https':raise ValueError('Public roster link must use HTTPS')
    return {'roster_url':url}


def export_locked():
    report=validate()
    current=read(REGISTRY/'current.json')
    configured=read(REGISTRY/'schools.json')['schools']
    schools=[{**{k:s[k] for k in ['institution_id','name','unit','headcount','incoming_headcount','current_headcount','observed_on','policy_id','roster_url','count_basis']},
              **public_roster_link(configured,s)} for s in current['schools'] if s['state']=='verified']
    public=ROOT/'site/faculty'
    if public.is_symlink() or (public.exists() and (not public.is_dir() or {p.name for p in public.iterdir()}!={'current.json','manifest.json'})):
        raise ValueError('Refusing to replace an unrelated faculty export path')
    from package_site import install_package_atomic, faculty_files
    with tempfile.TemporaryDirectory(prefix='.faculty-export-',dir=public.parent) as temporary:
        stage=Path(temporary)/'faculty';stage.mkdir()
        policy_id=read(REGISTRY/'policy.json')['id']
        metric_id=read(REGISTRY/'policy.json').get('metric_id','ece_regular_faculty')
        write_json(stage/'current.json',dict(schema_version=1,field='ece',policy_id=policy_id,metric_id=metric_id,schools=schools))
        write_json(stage/'manifest.json',dict(schema_version=1,field='ece',policy_id=policy_id,metric_id=metric_id,
            observation_id=current['observation_id'],validation=dict(status='passed',report_sha256=sha((REGISTRY/'validation.json').read_bytes())),
            artifacts={'current.json':{'sha256':sha((stage/'current.json').read_bytes())}}))
        faculty_files(Path(temporary))
        install_package_atomic(stage,public)
    print(f'Exported {len(schools)} verified current counts; publication data unchanged.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['build','validate','export'])
    args=parser.parse_args()
    if args.action=='build':build()
    elif args.action=='validate':validate()
    else:export()


if __name__=='__main__':main()
