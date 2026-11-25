"""Refresh safety: changed/failed sources must not silently replace accepted data."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pipeline'))
import faculty_refresh as refresh
import faculty_store as store
import faculty_registry as registry
import faculty_audit as audit


def directory(title='Professor',names=('Ada Example',),pager=''):
    cards=''.join(f'<div class="cc-image-list__item__content"><h3><a href="/people/{name.split()[0].lower()}">{name}</a></h3><strong>{title}</strong></div>' for name in names)
    return ('<main>'+cards+pager+'</main>').encode()


class FacultyRefreshTests(unittest.TestCase):
    def test_profile_projection_preserves_boston_primary_appointment(self):
        body = b'''<article><h1>Ada Example</h1>
            <h2 class="profile-single-title">Professor (BME, ECE)</h2>
            <li class="profile-details-primary-appointment">
                <span>Primary Appointment</span> Professor, Biomedical Engineering;
                Professor, Electrical and Computer Engineering</li></article>'''
        facts = refresh.projection(body, 'https://www.bu.edu/eng/profile/ada')['facts']
        self.assertEqual(facts['heading'], 'Ada Example')
        self.assertIn('Professor (BME, ECE)', facts['role_fields'])
        self.assertIn('Primary Appointment Professor, Biomedical Engineering; Professor, Electrical and Computer Engineering', facts['role_fields'])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.policy=json.loads((ROOT/'data/faculty/policy.json').read_text())
        store.atomic_json(self.root/'policy.json',self.policy)
        self.url='https://university.edu/faculty';self.profile='https://university.edu/people/ada'
        self.settings=dict(institution_id='https://openalex.org/I1',name='Example University',unit='ECE',country='US',adapter='berkeley',roster_url=self.url,max_pages=3,lists=[dict(id='roster',url=self.url,primary=True)])
        store.atomic_json(self.root/'schools.json',dict(schools={'example-u':self.settings}))
        self.responses={self.url:directory(),self.profile:b'<main><h1>Ada Example</h1><p>Professor of ECE</p></main>'}
        self.sources=[];self.evidence={}
        rows,_=refresh.parse_directory(self.responses[self.url],self.url,'berkeley')
        for url in self.responses:
            source,ref=refresh.record_source(self.root,self.fetch(url),directory_rows=rows if url==self.url else None)
            self.sources.append(source);self.evidence[url]=ref
        sid=self.sources[0]['id'];pid='person_example'
        self.person=dict(id=pid,legacy_ids=['example-u:ada'],display_name='Ada Example',names=['Ada Example'],profile_urls=[self.profile],identifiers=[],publication_links=[],conflicts=[],
            claims=[dict(id='claim_membership',property='department_membership',value='ECE',state='supported',source_ids=[sid],locator='Official ECE directory')],
            appointments=[dict(institution_id='https://openalex.org/I1',unit='ECE',category='regular',membership='ece',current_state='current',effective_from=None,effective_to=None,observed_on='2026-11-22',decision=dict(status='included',reason='Reviewed official ECE appointment',policy_id=self.policy['id'],source_ids=[s['id'] for s in self.sources],reviewers=['reviewer','independent'],independently_reviewed=True))])
        snapshot=dict(schema_version=1,school='example-u',institution_id='https://openalex.org/I1',name='Example University',unit='ECE',roster_url=self.url,observed_on='2026-11-22',policy_id=self.policy['id'],policy_sha256=store.digest((self.root/'policy.json').read_bytes()),config_sha256=store.digest(json.dumps(self.settings,sort_keys=True).encode()),parent=None,people=[self.person],sources=self.sources,evidence=self.evidence,roster=rows,lists={'roster':rows},failures=[],coverage={'complete':True},review={'reconciled':True,'kind':'validated_pilot_import'},diff={})
        self.baseline=store.put(self.root,'observations/example-u',snapshot)
        store.atomic_json(self.root/'accepted.json',dict(schema_version=1,schools={'example-u':self.baseline}))
        self.original=(self.root/'accepted.json').read_bytes()

    def fetch(self,url):
        body=self.responses[url]
        if isinstance(body,dict):return dict(url=url,observed_at='2026-11-22T23:00:00+00:00',**body)
        return dict(url=url,body=body,status=200,observed_at='2026-11-22T23:00:00+00:00')

    def observe(self):
        return refresh.observe(self.root,'example-u','2026-11-22',fetch=self.fetch,workers=1)

    def ready_review(self,path,independent=''):
        review=store.read(path)
        review.update(reviewer='Codex',independent_reviewer=independent,rationale='Reviewed source facts and membership',crosschecks_reviewed=True)
        store.atomic_json(path,review)
        self.complete_audit(review['observation'])
        return review

    def audit_result(self,candidate):
        """Synthetic second-agent output for offline fixtures; never real evidence."""
        state=store.read(audit.state_path(self.root,candidate));job=store.load_ref(self.root,state['job'])
        snapshot=store.load_ref(self.root,candidate);stamp=audit.utcnow()
        sources=[dict(id='fixture_'+str(i),url=item['url'],response_sha256='a'*64,observed_at=stamp,
            request_json=json.dumps(dict(method=item.get('method','GET'),form=item.get('form',{}))),locator='Synthetic independent test response')
            for i,item in enumerate(self.settings['lists'])]
        records=[]
        for person in snapshot['people']:
            if person['id'] not in job['scope']['required_person_ids']:continue
            a=person['appointments'][0]
            records.append(dict(person_id=person['id'],decision=a['decision']['status'],category=a['category'],membership=a['membership'],current_state=a['current_state'],effective_from_json=json.dumps(a['effective_from']),rationale='Synthetic independent test decision',source_ids=[s['id'] for s in sources]))
        result=dict(schema_version=1,job_id=job['job_id'],candidate_sha256=candidate['sha256'],reviewer_id='Fixture-independent-agent',reviewed_at=stamp,
            coverage=dict(complete=True,enumerated_profile_urls=[r['profile_url'] for r in snapshot['roster']],checked_list_ids=[x['id'] for x in self.settings['lists']]),records=records,sources=sources,findings=[])
        receipt=dict(job_id=job['job_id'],candidate_sha256=candidate['sha256'],transport='command',run_id='fixture-run',exit_code=0)
        return result,receipt

    def complete_audit(self,candidate):
        result,receipt=self.audit_result(candidate)
        return audit.import_result(self.root,candidate,result,receipt)

    def test_configured_school_and_date_are_not_fixed_to_pilot(self):
        _,snapshot,path=self.observe()
        self.assertEqual(snapshot['school'],'example-u')
        self.assertEqual(snapshot['diff']['changes'],[])

        self.ready_review(path)
        ref=refresh.accept_review(self.root,path)
        approved=store.load_ref(self.root,ref)
        self.assertEqual(approved['people'][0]['id'],self.person['id'])
        self.assertEqual(approved['review']['kind'],'unchanged_evidence_carry_forward')
        self.assertEqual(store.summarize(approved)['headcount'],1)
        for evidence in approved['evidence'].values():
            self.assertNotIn('body',store.load_ref(self.root,evidence))


    def test_separate_courtesy_roster_adds_candidates_in_union_mode(self):
        extra=self.url+'?type=courtesy'
        self.settings.update(roster_mode='union')
        self.settings['lists'].append(dict(id='courtesy',url=extra,primary=False))
        store.atomic_json(self.root/'schools.json',dict(schools={'example-u':self.settings}))
        self.responses[extra]=directory(title='Professor by courtesy',names=('Grace Example',))
        self.responses['https://university.edu/people/grace']=b'<main><h1>Grace Example</h1><p>ECE Professor by courtesy</p></main>'
        _,snapshot,_=self.observe()
        self.assertFalse(snapshot['failures'])
        self.assertEqual({p['display_name'] for p in snapshot['people']},{'Ada Example','Grace Example'})
        self.assertEqual(len(snapshot['roster']),2)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)
    def test_crosscheck_list_does_not_create_a_second_identity(self):
        graduate_url = self.url + '?type=graduate'
        self.settings.update(roster_mode='union')
        self.settings['lists'].append(dict(id='graduate', url=graduate_url,
                                           primary=False, crosscheck_only=True))
        store.atomic_json(self.root/'schools.json', dict(schools={'example-u':self.settings}))
        self.responses[graduate_url] = directory(names=('A. Example',))
        _, snapshot, _ = self.observe()
        self.assertEqual([row['name'] for row in snapshot['lists']['graduate']], ['A. Example'])
        self.assertEqual([row['name'] for row in snapshot['roster']], ['Ada Example'])
        self.assertFalse(snapshot['failures'])

    def test_post_category_requests_are_distinct_sources_with_explicit_provenance(self):
        base=dict(url=self.url,body=directory(),status=200,observed_at='2026-11-22T23:00:00+00:00')
        first={**base,'request':dict(method='POST',form={'faculty_type[]':'0'})}
        second={**base,'request':dict(method='POST',form={'faculty_type[]':'7'})}
        a,ar=refresh.record_source(self.root,first)
        b,br=refresh.record_source(self.root,second)
        self.assertNotEqual(a['id'],b['id'])
        self.assertNotEqual(ar,br)
        self.assertEqual(store.load_ref(self.root,ar)['request']['form'],{'faculty_type[]':'0'})
        self.assertNotEqual(refresh.list_key(refresh.request_key(first)),refresh.list_key(refresh.request_key(second)))

    def test_directory_entry_identities_do_not_collapse_people_sharing_a_source(self):
        self.settings['adapter']='michigan'
        store.atomic_json(self.root/'schools.json',dict(schools={'example-u':self.settings}))
        store.atomic_json(self.root/'accepted.json',dict(schools={}))
        self.responses[self.url]=('<main>'+''.join(
            '<div class="eecs_person_wrapper"><img src="/placeholder.jpg"><p class="eecs_person_name">'+name+'</p>'
            '<span class="person_title_section">Professor, Electrical and Computer Engineering</span></div>'
            for name in ('Ada Example','Grace Example'))+'</main>').encode()
        _,snapshot,_=self.observe()
        self.assertFalse(snapshot['failures'])
        self.assertEqual(len({p['id'] for p in snapshot['people']}),2)
        self.assertEqual({p['profile_urls'][0] for p in snapshot['people']},{self.url})
        self.assertTrue(all(p['profile_kind']=='official_directory_entry' for p in snapshot['people']))

    def test_browser_dom_capture_does_not_claim_an_origin_response_hash_or_status(self):
        result=dict(url=self.url,body=b'<main><h1>Official faculty</h1></main>',status=None,
                    observed_at='2026-11-22T23:00:00+00:00',capture_format='browser_dom',capture_tool='synthetic-browser-fixture')
        source,ref=refresh.record_source(self.root,result)
        evidence=store.load_ref(self.root,ref)
        for value in (source,evidence):
            self.assertIsNone(value['response_sha256'])
            self.assertIsNone(value['http_status'])
            self.assertEqual(value['capture_sha256'],store.digest(result['body']))
        with self.assertRaisesRegex(ValueError,'unavailable HTTP status'):
            refresh.record_source(self.root,{**result,'status':200})

    def test_browser_audit_requires_exact_pinned_capture_metadata(self):
        candidate,_,path=self.observe();self.ready_review(path)
        result,receipt=self.audit_result(candidate);source=result['sources'][0];old_id=source['id']
        source.update(id='shared_browser_fixture',response_sha256=None,capture_format='browser_dom',
                      capture_sha256='d'*64,capture_tool='synthetic-browser-fixture')
        for row in result['records']:row['source_ids']=[source['id'] if sid==old_id else sid for sid in row['source_ids']]
        with self.assertRaisesRegex(ValueError,'pinned host capture'):
            audit.import_result(self.root,candidate,result,receipt)
        packet=dict(job_id=result['job_id'],candidate_sha256=candidate['sha256'],records=[{
            **source,'request':json.loads(source['request_json'])}])
        receipt.update(review_mode='independent_judgment_of_shared_captures',capture_packet=store.put(self.root,'audits/packets',packet))
        audit.import_result(self.root,candidate,result,receipt)
        refresh.accept_review(self.root,path)
        source['capture_sha256']='e'*64
        with self.assertRaisesRegex(ValueError,'Browser DOM source differs'):
            audit.import_result(self.root,candidate,result,receipt)

    def test_collection_keeps_multiple_post_filters_at_the_same_url_separate(self):
        self.settings['lists']=[dict(id='all',url=self.url,method='POST',form={'faculty_type[]':'0'},primary=True),dict(id='regular',url=self.url,method='POST',form={'faculty_type[]':'7'},primary=False)]
        store.atomic_json(self.root/'schools.json',dict(schools={'example-u':self.settings}))
        def fetch(target):
            if isinstance(target,str):return self.fetch(target)
            return dict(url=target['url'],request={'method':target['method'],'form':target['form']},body=directory(),status=200,observed_at='2026-11-22T23:00:00+00:00')
        _,snapshot,_=refresh.observe(self.root,'example-u','2026-11-22',fetch=fetch,workers=1)
        self.assertFalse(snapshot['failures'])
        self.assertEqual(set(snapshot['lists']),{'all','regular'})
        requests=[source['request']['form']['faculty_type[]'] for source in snapshot['sources'] if source.get('request')]
        self.assertCountEqual(requests,['0','7'])
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_usc_card_parser_preserves_names_and_professorship_titles(self):
        body=b'<main><div id="results"><a href="/directory/faculty/Example/Ada"><div class="faculty-member"><div class="faculty-text"><h5 class="resultName">Ada Example</h5>Professor of Electrical and Computer Engineering</div></div></a></div></main>'
        rows,last=refresh.parse_directory(body,'https://viterbi.usc.edu/directory/faculty/','usc')
        self.assertEqual(rows,[dict(name='Ada Example',title='Professor of Electrical and Computer Engineering',profile_url='https://viterbi.usc.edu/directory/faculty/Example/Ada')])
        self.assertEqual(last,0)

    def test_usc_ignored_post_filter_is_a_failure_not_a_valid_category(self):
        result=dict(request=dict(method='POST',form={'faculty_type[]':'0'}),body=b'<select name="faculty_type[]"><option value="7" selected>Tenure track</option></select>')
        with self.assertRaisesRegex(ValueError,'filter not applied'):refresh.verify_usc_filters(result)
        result['body']=b'<select name="faculty_type[]"><option value="0" selected>All</option></select>'
        refresh.verify_usc_filters(result)

    def test_usc_blank_title_is_retained_but_empty_primary_is_still_rejected(self):
        body=b'<div id="results"><a href="/directory/faculty/Example/Ada"><div class="faculty-member"><div class="faculty-text"><span class="resultName">Ada Example</span><div></div></div></div></a></div>'
        rows,_=refresh.parse_directory(body,self.url,'usc')
        self.assertEqual(rows[0]['title'],'')
        empty=b'<div id="results"></div>'
        self.assertEqual(refresh.parse_directory(empty,self.url,'usc',allow_empty=True),([],0))
        with self.assertRaisesRegex(ValueError,'No directory entries'):refresh.parse_directory(empty,self.url,'usc')

    def test_explicit_profile_alias_preserves_identity_and_original_directory_link(self):
        correct='https://university.edu/people/ada-correct'
        self.settings['profile_url_aliases']={self.profile:correct}
        store.atomic_json(self.root/'schools.json',dict(schools={'example-u':self.settings}))
        # A new-school observation has no accepted identity to overwrite.
        store.atomic_json(self.root/'accepted.json',dict(schema_version=1,schools={}))
        self.responses[self.profile]={'error':'Bad directory link','status':404}
        self.responses[correct]=b'<main><h1>Ada Example</h1><p>Professor of ECE</p></main>'
        _,snapshot,_=self.observe()
        self.assertFalse(snapshot['failures'])
        person=snapshot['people'][0]
        self.assertEqual(person['id'],refresh.stable_id('person',self.profile))
        self.assertEqual(person['profile_urls'],[self.profile,correct])
        self.assertEqual(snapshot['roster'][0]['profile_url'],self.profile)
        self.assertEqual(snapshot['profile_url_aliases'],{self.profile:correct})

    def test_reviewed_ambiguity_is_saved_without_approving_a_count(self):
        self.responses[self.profile]=b'<main><h1>Ada Example</h1><p>Joint secondary appointment; courtesy status unclear.</p></main>'
        _,snapshot,path=self.observe();review=self.ready_review(path,'Astra')
        person=snapshot['people'][0];appointment=copy.deepcopy(person['appointments'][0])
        appointment.update(category='unresolved',current_state='unknown')
        appointment['decision'].update(status='unresolved',independently_reviewed=False)
        review['decisions']=[dict(person_id=person['id'],appointment=appointment,claims=[])]
        store.atomic_json(path,review)
        ref,statuses=refresh.review_draft(self.root,path)
        draft=store.load_ref(self.root,ref)
        self.assertEqual(statuses['unresolved'],1)
        self.assertIsNone(store.summarize(draft)['headcount'])
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)
        with self.assertRaisesRegex(ValueError,'Independent audit blocks'):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_unavailable_profile_never_removes_person_or_changes_accepted_count(self):
        self.responses[self.profile]={'error':'HTTP 503','status':503}
        _,snapshot,path=self.observe()
        self.assertEqual(len(snapshot['people']),1)
        self.assertFalse(snapshot['coverage']['complete'])
        self.ready_review(path,'Astra')
        with self.assertRaisesRegex(ValueError,'Failed collection'):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_empty_or_changed_directory_layout_is_failure_not_zero(self):
        self.responses[self.url]=b'<main>Temporarily unavailable</main>'
        _,snapshot,path=self.observe()
        self.assertTrue(snapshot['failures'])
        self.ready_review(path,'Astra')
        with self.assertRaises(ValueError):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_courtesy_change_is_held_for_independent_review(self):
        self.responses[self.profile]=b'<main><h1>Ada Example</h1><p>Professor by courtesy in ECE</p></main>'
        _,snapshot,path=self.observe()
        self.assertEqual(len(snapshot['diff']['changes']),1)
        self.assertEqual(snapshot['people'][0]['appointments'][0]['decision']['status'],'unresolved')
        review=self.ready_review(path)
        appointment=copy.deepcopy(snapshot['people'][0]['appointments'][0])
        review['decisions']=[dict(person_id=snapshot['people'][0]['id'],appointment=appointment,claims=[])]
        store.atomic_json(path,review)
        with self.assertRaisesRegex(ValueError,'[Ii]ndependent audit'):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_appointment_changes_in_profile_header_or_sidebar_are_not_ignored(self):
        for tag in ['header','aside']:
            with self.subTest(tag=tag):
                self.responses[self.profile]=f'<main><h1>Ada Example</h1><p>Professor of ECE</p><{tag}>Professor by courtesy</{tag}></main>'.encode()
                _,snapshot,_=self.observe()
                self.assertEqual(len(snapshot['diff']['changes']),1)

    def test_missing_directory_entry_requires_positive_departure_evidence(self):
        self.responses[self.url]=directory(names=('Ben Example',))
        self.responses['https://university.edu/people/ben']=b'<main>Ben Example, Professor of ECE</main>'
        _,snapshot,path=self.observe();review=self.ready_review(path,'Astra')
        for person in snapshot['people']:
            appointment=copy.deepcopy(person['appointments'][0])
            appointment.update(category='departed',membership='ece',current_state='past')
            appointment['decision'].update(status='excluded',independently_reviewed=True)
            review['decisions'].append(dict(person_id=person['id'],appointment=appointment,claims=[]))
        store.atomic_json(path,review)
        with self.assertRaisesRegex(ValueError,'absence alone'):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_previously_departed_person_is_preserved_without_being_rediscovered(self):
        baseline=store.load_ref(self.root,self.baseline)
        appointment=baseline['people'][0]['appointments'][0]
        appointment.update(category='departed',current_state='past')
        appointment['decision']['status']='excluded'
        baseline['roster']=[];baseline['lists']={'roster':[]}
        ref=store.put(self.root,'observations/example-u',baseline)
        store.atomic_json(self.root/'accepted.json',dict(schools={'example-u':ref}))
        self.responses[self.url]=directory(names=('Ben Example',))
        self.responses[self.profile]={'error':'Old profile removed','status':404}
        self.responses['https://university.edu/people/ben']=b'<main>Ben Example, Professor of ECE</main>'
        _,snapshot,_=self.observe()
        self.assertFalse(snapshot['failures'])
        self.assertEqual([c['name'] for c in snapshot['diff']['changes']],['Ben Example'])
        retained=next(p for p in snapshot['people'] if p['id']==self.person['id'])
        self.assertEqual(retained['appointments'][0]['current_state'],'past')

    def test_missing_page_and_duplicate_page_members_fail_closed(self):
        self.responses[self.url]=directory(pager='<a href="?page=1">Next</a>')
        page=refresh.page_url(self.url,1)
        self.responses[page]={'error':'HTTP 404','status':404}
        _,snapshot,_=self.observe();self.assertTrue(snapshot['failures'])
        self.responses[page]=directory()
        _,snapshot,_=self.observe()
        self.assertTrue(any('Duplicate profile' in e['error'] for e in snapshot['failures']))
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_secondary_category_change_cannot_hide_behind_unchanged_primary_roster(self):
        core='https://university.edu/core'
        self.settings['lists'].append(dict(id='core',url=core,primary=False))
        store.atomic_json(self.root/'schools.json',dict(schools={'example-u':self.settings}))
        baseline=store.load_ref(self.root,self.baseline)
        baseline['lists']['core']=baseline['roster']
        baseline['config_sha256']=store.digest(json.dumps(self.settings,sort_keys=True).encode())
        ref=store.put(self.root,'observations/example-u',baseline)
        store.atomic_json(self.root/'accepted.json',dict(schools={'example-u':ref}))
        self.responses[core]=directory(title='Professor by courtesy')
        _,snapshot,path=self.observe()
        self.assertEqual(snapshot['diff']['crosscheck_changes'],['core'])
        self.assertIn('official_category_membership_or_title_changed',snapshot['diff']['changes'][0]['reasons'])
        review=self.ready_review(path)
        review['decisions']=[dict(person_id=snapshot['people'][0]['id'],appointment=snapshot['people'][0]['appointments'][0],claims=[])]
        store.atomic_json(path,review)
        with self.assertRaisesRegex(ValueError,'[Ii]ndependent audit'):refresh.accept_review(self.root,path)

    def test_incoming_status_and_announced_date_survive_refresh(self):
        baseline=store.load_ref(self.root,self.baseline)
        person=baseline['people'][0];appointment=person['appointments'][0]
        appointment.update(current_state='incoming',effective_from={'year':2027,'precision':'year'})
        person['claims'].append(dict(id='claim_incoming',property='appointment_state',value='incoming',state='supported',source_ids=[self.sources[0]['id']],locator='Official incoming appointment fixture'))
        ref=store.put(self.root,'observations/example-u',baseline)
        store.atomic_json(self.root/'accepted.json',dict(schools={'example-u':ref}))
        _,_,path=self.observe();self.ready_review(path)
        refreshed=store.load_ref(self.root,refresh.accept_review(self.root,path))
        appointment=refreshed['people'][0]['appointments'][0]
        self.assertEqual(appointment['current_state'],'incoming')
        self.assertEqual(appointment['effective_from']['year'],2027)
        self.assertEqual(store.summarize(refreshed)['incoming_headcount'],1)

    def test_observation_cannot_be_backdated_or_relabelled_after_collection(self):
        _,snapshot,path=refresh.observe(self.root,'example-u','2025-01-01',fetch=self.fetch,workers=1)
        self.assertFalse(snapshot['coverage']['complete'])
        self.ready_review(path)
        with self.assertRaisesRegex(ValueError,'Failed collection'):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_policy_change_and_tampered_evidence_cannot_be_accepted(self):
        _,snapshot,path=self.observe();self.ready_review(path)
        self.policy['version']=999;store.atomic_json(self.root/'policy.json',self.policy)
        with self.assertRaisesRegex(ValueError,'policy.*changed'):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)
        evidence=next(iter(snapshot['evidence'].values()))
        (self.root/evidence['file']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'checksum'):store.load_ref(self.root,evidence)

    def legacy_baseline(self):
        body=(ROOT/'data/faculty/policies/us-ece-current-v3.json').read_bytes()
        legacy=json.loads(body)
        store.atomic_write(self.root/'policies'/f"{legacy['id']}.json",body)
        snapshot=store.load_ref(self.root,self.baseline)
        snapshot.update(policy_id=legacy['id'],policy_sha256=store.digest(body))
        for person in snapshot['people']:
            for appointment in person['appointments']:appointment['decision']['policy_id']=legacy['id']
        ref=store.put(self.root,'observations/example-u',snapshot)
        store.atomic_json(self.root/'accepted.json',dict(schools={'example-u':ref}))
        return snapshot,legacy

    def test_legacy_observation_remains_valid_evidence_but_cannot_be_accepted_as_current(self):
        snapshot,legacy=self.legacy_baseline()
        with self.assertRaisesRegex(ValueError,'policy changed'):
            store.check_snapshot(self.root,snapshot,legacy,registry.validate_people)
        summary=store.check_snapshot(self.root,snapshot,legacy,registry.validate_people,allow_historical_policy=True)
        self.assertEqual(summary['headcount'],1)
        self.assertEqual(summary['metric_id'],'ece_regular_faculty')
        store.atomic_json(self.root/'policies'/f"{legacy['id']}.json",{**legacy,'version':999})
        with self.assertRaisesRegex(ValueError,'checksum differs'):
            store.check_snapshot(self.root,snapshot,legacy,registry.validate_people,allow_historical_policy=True)

    def test_policy_migration_requires_a_new_decision_even_with_unchanged_sources(self):
        self.legacy_baseline()
        _,snapshot,_=self.observe()
        appointment=snapshot['people'][0]['appointments'][0]
        self.assertEqual(appointment['decision']['policy_id'],self.policy['id'])
        self.assertEqual(appointment['decision']['status'],'unresolved')
        self.assertIn('policy_changed',snapshot['diff']['changes'][0]['reasons'])

    def test_courtesy_and_unspecified_joint_appointments_can_pass_a_fresh_audit(self):
        for category in ('courtesy','joint_secondary'):
            with self.subTest(category=category):
                self.responses[self.profile]=f'<main><h1>Ada Example</h1><p>ECE Professor: {category}</p></main>'.encode()
                candidate,snapshot,path=self.observe()
                review=store.read(path)
                appointment=copy.deepcopy(snapshot['people'][0]['appointments'][0])
                appointment.update(category=category,membership='ece',current_state='current')
                appointment['decision'].update(status='included',reason='Official professorial ECE affiliation independently reviewed',independently_reviewed=True)
                review.update(reviewer='Collector',rationale='Reconciled the independent appointment review',crosschecks_reviewed=True,
                              decisions=[dict(person_id=self.person['id'],appointment=appointment,claims=[])])
                store.atomic_json(path,review)
                result,receipt=self.audit_result(candidate)
                result['records'][0].update(decision='included',category=category,membership='ece',current_state='current')
                audit.import_result(self.root,candidate,result,receipt)
                approved=store.load_ref(self.root,refresh.accept_review(self.root,path))
                summary=store.summarize(approved)
                self.assertEqual(summary['headcount'],1)
                self.assertEqual(summary['metric_id'],'ece_affiliated_faculty')
                self.assertEqual(approved['people'][0]['appointments'][0]['category'],category)
        # A completed agent audit remains readable under its pinned policy after
        # an upgrade, but that permission cannot authorize a new acceptance.
        body=(self.root/'policy.json').read_bytes()
        store.atomic_write(self.root/'policies'/f"{self.policy['id']}.json",body)
        store.atomic_json(self.root/'policy.json',{**self.policy,'id':'example-next-policy','version':5})
        historical=store.check_snapshot(self.root,approved,self.policy,registry.validate_people,allow_historical_policy=True)
        self.assertEqual(historical['headcount'],1)
        with self.assertRaisesRegex(ValueError,'policy changed'):
            store.check_snapshot(self.root,approved,self.policy,registry.validate_people)

    def test_registry_retains_legacy_people_but_withholds_the_broader_count(self):
        snapshot,legacy=self.legacy_baseline()
        iid=next(i for i,value in registry.read(ROOT/'site/data/institutions.json').items() if value.get('country')=='US')
        snapshot['institution_id']=iid
        snapshot['people'][0]['appointments'][0]['institution_id']=iid
        ref=store.put(self.root,'observations/example-u',snapshot)
        store.atomic_json(self.root/'accepted.json',dict(schools={'example-u':ref}))
        before=(self.root/'accepted.json').read_bytes()
        with patch.object(registry,'REGISTRY',self.root):
            _,people,_,summaries=registry.accepted_components()
        self.assertEqual(people,snapshot['people'])
        self.assertEqual(summaries[0]['state'],'needs_update')
        self.assertIsNone(summaries[0]['headcount'])
        self.assertEqual(summaries[0]['previous_count']['headcount'],1)
        self.assertEqual(summaries[0]['target_policy_id'],self.policy['id'])
        self.assertEqual((self.root/'accepted.json').read_bytes(),before)

    def test_stale_review_cannot_overwrite_a_newer_accepted_observation(self):
        _,_,first=self.observe();_,_,second=self.observe()
        self.ready_review(first);self.ready_review(second)
        refresh.accept_review(self.root,first)
        current=(self.root/'accepted.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'Stale review'):refresh.accept_review(self.root,second)
        self.assertEqual((self.root/'accepted.json').read_bytes(),current)

    def test_failed_pointer_write_retains_previous_accepted_observation(self):
        _,_,path=self.observe();self.ready_review(path)
        actual=store.atomic_json
        def fail_pointer(destination,value):
            if Path(destination).name=='accepted.json':raise OSError('simulated disk failure')
            return actual(destination,value)
        with patch.object(refresh,'atomic_json',side_effect=fail_pointer):
            with self.assertRaises(OSError):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_export_validation_failure_preserves_public_bundle(self):
        public=self.root/'site/faculty';public.mkdir(parents=True)
        (public/'current.json').write_text('previous count bundle')
        (public/'manifest.json').write_text('previous manifest')
        store.atomic_json(self.root/'current.json',dict(observation_id='test',schools=[]))
        store.atomic_json(self.root/'validation.json',dict(status='passed'))
        with patch.object(registry,'REGISTRY',self.root),patch.object(registry,'ROOT',self.root),patch.object(registry,'validate',return_value={'status':'passed'}),patch('package_site.faculty_files',side_effect=ValueError('injected export validation failure')):
            with self.assertRaisesRegex(ValueError,'injected'):registry.export()
        self.assertEqual((public/'current.json').read_text(),'previous count bundle')
        self.assertEqual((public/'manifest.json').read_text(),'previous manifest')

    def test_artifact_cannot_escape_store_or_be_changed_in_place(self):
        with self.assertRaisesRegex(ValueError,'escapes'):store.load_ref(self.root,dict(file='../private',sha256='0'*64))
        ref=store.put(self.root,'evidence',{'fact':'Professor'})
        (self.root/ref['file']).write_text('corrupted')
        with self.assertRaisesRegex(ValueError,'Immutable'):store.put(self.root,'evidence',{'fact':'Professor'})

    def test_a_reviewer_name_without_an_agent_result_cannot_accept_even_unchanged_data(self):
        candidate,_,path=self.observe()
        review=store.read(path)
        review.update(reviewer='Collector',independent_reviewer='Astra',rationale='A name is insufficient',crosschecks_reviewed=True)
        store.atomic_json(path,review)
        self.assertEqual(store.read(audit.state_path(self.root,candidate))['status'],'pending')
        with self.assertRaisesRegex(ValueError,'audit has not completed'):refresh.accept_review(self.root,path)
        draft,_=refresh.review_draft(self.root,path)
        self.assertIsNone(store.summarize(store.load_ref(self.root,draft))['headcount'])
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_new_school_gets_a_full_blind_audit(self):
        store.atomic_json(self.root/'accepted.json',dict(schools={}))
        candidate,snapshot,_=self.observe();state=store.read(audit.state_path(self.root,candidate))
        job=store.load_ref(self.root,state['job']);brief=store.load_ref(self.root,state['brief'])
        self.assertEqual(job['scope']['kind'],'full_roster')
        self.assertEqual(set(job['scope']['required_person_ids']),{p['id'] for p in snapshot['people']})
        self.assertEqual(job['scope']['sampled_person_ids'],[])
        self.assertEqual(set(brief['people'][0]),{'person_id','name','profile_urls'})
        for key in ('diff','parent','headcount','decisions','appointments','review'):self.assertNotIn(key,brief)
        self.assertEqual(audit.prepare(self.root,candidate),state)

    def test_refresh_sample_is_seeded_and_all_changes_are_required(self):
        baseline=store.load_ref(self.root,self.baseline);names=[f'Person{i} Example' for i in range(35)]
        self.responses[self.url]=directory(names=names)
        rows,_=refresh.parse_directory(self.responses[self.url],self.url,'berkeley')
        baseline['people']=[];baseline['roster']=rows;baseline['lists']={'roster':rows}
        for i,row in enumerate(rows):
            person=copy.deepcopy(self.person)
            person.update(id=f'person_{i}',display_name=row['name'],names=[row['name']],profile_urls=[row['profile_url']])
            baseline['people'].append(person)
            self.responses[row['profile_url']]=self.responses[self.profile]
        ref=store.put(self.root,'observations/example-u',baseline)
        store.atomic_json(self.root/'accepted.json',dict(schools={'example-u':ref}))
        self.responses[self.url]=directory(names=names,title='Professor of ECE')
        # All title changes must be included even when the sample is capped.
        candidate,snapshot,_=self.observe();job=store.load_ref(self.root,store.read(audit.state_path(self.root,candidate))['job'])
        changed={r['person_id'] for r in snapshot['diff']['changes']}
        self.assertEqual(changed,set(job['scope']['required_person_ids']))
        self.responses[self.url]=directory(names=names)
        candidate,snapshot,_=self.observe();job=store.load_ref(self.root,store.read(audit.state_path(self.root,candidate))['job'])
        scope=job['scope'];self.assertEqual(scope['changed_person_ids'],[])
        expected=sorted([p['id'] for p in snapshot['people']],key=lambda pid:store.digest((scope['seed']+pid).encode()))[:10]
        self.assertEqual(set(scope['sampled_person_ids']),set(expected))
        path=self.root/'pending-reviews'/Path(candidate['file']).name
        review=self.ready_review(path)
        unsampled=next(p for p in snapshot['people'] if p['id'] not in scope['required_person_ids'])
        review['decisions']=[dict(person_id=unsampled['id'],appointment=unsampled['appointments'][0],claims=[])]
        store.atomic_json(path,review)
        with self.assertRaisesRegex(ValueError,'expanded independent audit'):refresh.accept_review(self.root,path)
        state=audit.prepare(self.root,candidate,force=True,full=True)
        self.assertEqual(len(store.load_ref(self.root,state['job'])['scope']['required_person_ids']),35)

    def test_bad_or_stale_independent_results_are_rejected(self):
        candidate,_,_=self.observe();result,receipt=self.audit_result(candidate)
        mutations=[lambda x:x.update(job_id='older-job'),lambda x:x.update(candidate_sha256='0'*64),
            lambda x:x.update(reviewer_id='collector'),lambda x:x['records'].append(copy.deepcopy(x['records'][0])),
            lambda x:x.update(records=[]),lambda x:x['sources'][0].update(response_sha256='unavailable'),
            lambda x:x['sources'][0].update(observed_at='2020-01-01T00:00:00Z'),
            lambda x:x['records'][0].update(source_ids=['unknown-source']),lambda x:x.update(extra='not allowed')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                bad=copy.deepcopy(result);mutate(bad)
                with self.assertRaises(ValueError):audit.import_result(self.root,candidate,bad,receipt)
        with self.assertRaises(ValueError):audit.import_result(self.root,candidate,result,{**receipt,'exit_code':1})
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_incomplete_enumeration_categories_or_post_provenance_block_acceptance(self):
        candidate,_,path=self.observe();self.ready_review(path)
        result,receipt=self.audit_result(candidate)
        mutations=[lambda x:x['coverage'].update(complete=False),lambda x:x['coverage'].update(enumerated_profile_urls=[]),
            lambda x:x['coverage'].update(checked_list_ids=[]),
            lambda x:x['sources'][0].update(request_json=json.dumps(dict(method='POST',form={'wrong':'filter'}))),
            lambda x:x['findings'].append(dict(kind='omission',person_id='',description='Official incoming appointment omitted')),
            lambda x:x['findings'].append(dict(kind='source_failure',person_id='',description='Official announcement inaccessible'))]
        for mutate in mutations:
            bad=copy.deepcopy(result);mutate(bad);audit.import_result(self.root,candidate,bad,receipt)
            with self.assertRaisesRegex(ValueError,'Independent audit blocks'):refresh.accept_review(self.root,path)
            self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_primary_must_reconcile_the_independent_recommendation(self):
        candidate,snapshot,path=self.observe();review=self.ready_review(path)
        result,receipt=self.audit_result(candidate)
        result['records'][0].update(decision='excluded',category='adjunct',current_state='not_in_core')
        audit.import_result(self.root,candidate,result,receipt)
        with self.assertRaisesRegex(ValueError,'unreconciled audit decision'):refresh.accept_review(self.root,path)
        replacement=copy.deepcopy(snapshot['people'][0]['appointments'][0])
        replacement.update(category='adjunct',current_state='not_in_core')
        replacement['decision'].update(status='excluded',reason='Official adjunct appointment independently checked')
        review['decisions']=[dict(person_id=snapshot['people'][0]['id'],appointment=replacement,claims=[])]
        store.atomic_json(path,review)
        accepted=store.load_ref(self.root,refresh.accept_review(self.root,path))
        self.assertEqual(store.summarize(accepted)['headcount'],0)
        self.assertEqual(accepted['review']['independent_reviewer'],'Fixture-independent-agent')
        dependencies=store.dependencies(self.root,accepted)
        self.assertIn(accepted['review']['audit']['file'],dependencies)

    def test_primary_reviewer_cannot_be_the_independent_agent(self):
        _,_,path=self.observe();review=self.ready_review(path)
        review['reviewer']='Fixture-independent-agent';store.atomic_json(path,review)
        with self.assertRaisesRegex(ValueError,'Primary reviewer cannot'):refresh.accept_review(self.root,path)

    def test_emeritus_label_difference_is_not_a_count_disagreement(self):
        baseline=store.load_ref(self.root,self.baseline)
        appointment=baseline['people'][0]['appointments'][0]
        appointment.update(category='emeritus',current_state='past')
        appointment['decision']['status']='excluded'
        baseline_ref=store.put(self.root,'observations/example-u',baseline)
        store.atomic_json(self.root/'accepted.json',dict(schools={'example-u':baseline_ref}))
        candidate,_,path=self.observe();self.ready_review(path)
        result,receipt=self.audit_result(candidate)
        result['records'][0]['current_state']='not_in_core'
        audit.import_result(self.root,candidate,result,receipt)
        accepted=store.load_ref(self.root,refresh.accept_review(self.root,path))
        self.assertEqual(store.summarize(accepted)['headcount'],0)
        self.assertEqual(accepted['people'][0]['appointments'][0]['current_state'],'past')
        # This narrow equivalence must not hide incoming/current or category differences.
        for status,category in [('included','regular'),('excluded','courtesy'),('excluded','departed')]:
            self.assertNotEqual(audit.appointment_signature(status,category,'ece','past',None),audit.appointment_signature(status,category,'ece','not_in_core',None))
        self.assertEqual(audit.appointment_signature('excluded','teaching','ece','current',None),audit.appointment_signature('excluded','teaching','ece','not_in_core',None))
        self.assertEqual(audit.appointment_signature('excluded','emeritus','ece','current',None),audit.appointment_signature('excluded','emeritus','ece','past',None))
        self.assertNotEqual(audit.appointment_signature('included','regular','ece','current',None),audit.appointment_signature('included','regular','ece','incoming',None))

    def test_explicit_host_handoff_keeps_the_audit_gate_closed(self):
        store.atomic_json(self.root/'audit-config.json',dict(runner=dict(kind='codex',model='gpt-6.1-terra')))
        with patch.object(audit,'run',side_effect=AssertionError('Host handoff must not start a second CLI agent')):
            candidate,_,path=refresh.observe(self.root,'example-u','2026-11-22',fetch=self.fetch,workers=1,audit_transport='handoff')
        self.assertEqual(store.read(audit.state_path(self.root,candidate))['status'],'pending')
        review=store.read(path);review.update(reviewer='Collector',rationale='Host-managed review pending',crosschecks_reviewed=True)
        store.atomic_json(path,review)
        with self.assertRaisesRegex(ValueError,'audit has not completed'):refresh.accept_review(self.root,path)

    def test_unreviewed_inclusion_can_be_saved_only_as_an_unpublished_draft(self):
        candidate,snapshot,path=self.observe();review=self.ready_review(path)
        person=snapshot['people'][0];appointment=copy.deepcopy(person['appointments'][0])
        appointment['decision']['independently_reviewed']=False
        review['decisions']=[dict(person_id=person['id'],appointment=appointment,claims=[])]
        store.atomic_json(path,review)
        draft,_=refresh.review_draft(self.root,path)
        self.assertIsNone(store.summarize(store.load_ref(self.root,draft))['headcount'])
        with self.assertRaisesRegex(ValueError,'independent review'):refresh.accept_review(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_followup_source_leads_are_pinned_without_collector_verdicts(self):
        candidate,_,_=self.observe()
        state=audit.prepare(self.root,candidate,force=True,evidence_urls=['https://university.edu/faculty-cv.pdf'])
        job=store.load_ref(self.root,state['job']);brief=store.load_ref(self.root,state['brief'])
        self.assertEqual(job['evidence_urls'],['https://university.edu/faculty-cv.pdf'])
        self.assertIn('https://university.edu/faculty-cv.pdf',brief['supporting_urls'])
        self.assertNotIn('decisions',brief)

    def test_supplemental_evidence_is_hashed_dated_and_bound_to_its_source(self):
        candidate,snapshot,path=self.observe();review=self.ready_review(path)
        result=dict(url='https://university.edu/new-appointment',body=b'<main>Official appointment clarification</main>',status=200,observed_at='2026-11-22T23:00:00+00:00')
        source,evidence=refresh.record_source(self.root,result)
        review['supplemental_sources']=[dict(source=source,evidence=evidence)]
        store.atomic_json(path,review)
        draft,_=refresh.review_draft(self.root,path)
        self.assertIn(evidence['file'],store.dependencies(self.root,store.load_ref(self.root,draft)))
        review['supplemental_sources'][0]['source']['response_sha256']='0'*64
        store.atomic_json(path,review)
        with self.assertRaisesRegex(ValueError,'immutable evidence'):refresh.review_draft(self.root,path)
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_shared_capture_review_preserves_origin_and_candidate_binding(self):
        candidate,_,path=self.observe();self.ready_review(path)
        result,receipt=self.audit_result(candidate);source=result['sources'][0]
        original=source['id'];source['id']='shared_fixture'
        for record in result['records']:record['source_ids']=['shared_fixture' if sid==original else sid for sid in record['source_ids']]
        with self.assertRaisesRegex(ValueError,'pinned capture packet'):audit.import_result(self.root,candidate,result,receipt)
        packet=dict(job_id=result['job_id'],candidate_sha256=candidate['sha256'],capture_origin='Synthetic collector capture for independent judgment',records=[dict(id=source['id'],url=source['url'],response_sha256=source['response_sha256'],observed_at=source['observed_at'],request=json.loads(source['request_json']))])
        receipt.update(review_mode='independent_judgment_of_shared_captures',capture_packet=store.put(self.root,'audits/packets',packet))
        audit.import_result(self.root,candidate,result,receipt)
        approved=store.load_ref(self.root,refresh.accept_review(self.root,path))
        self.assertIn(receipt['capture_packet']['file'],store.dependencies(self.root,approved))
        result['sources'][0]['response_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'differs from the captured evidence'):audit.import_result(self.root,candidate,result,receipt)

    def test_schema_valid_but_evidence_contradicting_audit_can_be_rejected(self):
        candidate,snapshot,path=self.observe();self.ready_review(path)
        result,receipt=self.audit_result(candidate)
        rejection=dict(reviewer='Primary-assessor',reason='Reviewer ignored explicit appointment-type evidence',findings=[dict(person_id=result['records'][0]['person_id'],description='Synthetic official appointment evidence contradicts the reviewer recommendation',source_ids=result['records'][0]['source_ids'])])
        ref=audit.import_result(self.root,candidate,result,receipt,rejection=rejection)
        self.assertEqual(store.read(audit.state_path(self.root,candidate))['status'],'rejected')
        with self.assertRaisesRegex(ValueError,'audit was rejected'):refresh.accept_review(self.root,path)
        draft,_=refresh.review_draft(self.root,path)
        self.assertIsNone(store.summarize(store.load_ref(self.root,draft))['headcount'])
        # Immutable rejection also blocks a stored bundle independently of mutable state.
        self.assertIn(ref['file'],store.dependencies(self.root,store.load_ref(self.root,draft)))
        with self.assertRaisesRegex(ValueError,'audit was rejected'):audit.check_bundle(self.root,ref,candidate,store.read(path),snapshot)
        # Keep an invalid timestamp exactly as returned instead of repairing it
        # into an apparently fresh review. The immutable artifact stays rejected.
        result['reviewed_at']='2020-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'Stale audit timestamp'):audit.import_result(self.root,candidate,result,receipt)
        rejected=audit.import_result(self.root,candidate,result,receipt,rejection=rejection)
        bundle=store.load_ref(self.root,rejected)
        self.assertEqual(bundle['result']['reviewed_at'],'2020-01-01T00:00:00Z')
        self.assertIn('Stale audit timestamp',bundle['assessment']['validation_errors'])
        self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_new_audit_job_invalidates_old_result_but_not_accepted_history(self):
        candidate,_,path=self.observe();self.ready_review(path)
        result,receipt=self.audit_result(candidate)
        approved=store.load_ref(self.root,refresh.accept_review(self.root,path))
        audit.prepare(self.root,candidate,force=True)
        with self.assertRaisesRegex(ValueError,'another job'):audit.import_result(self.root,candidate,result,receipt)
        # Immutable historical acceptance remains verifiable after a later audit.
        store.check_snapshot(self.root,approved,self.policy,registry.validate_people)
        ref=store.put(self.root,'observations/example-u',approved)
        (self.root/ref['file']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'checksum'):store.load_ref(self.root,ref)

    def test_observe_automatically_starts_a_separate_command_agent(self):
        program='''import json,sys,datetime
x=json.load(sys.stdin);b=x['brief'];stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
sources=[dict(id='test-source',url=b['lists'][0]['url'],response_sha256='a'*64,observed_at=stamp,request_json=json.dumps(dict(method='GET',form={})),locator='Synthetic subprocess test')]
records=[dict(person_id=p['person_id'],decision='included',category='regular',membership='ece',current_state='current',effective_from_json='null',rationale='Synthetic subprocess appointment',source_ids=['test-source']) for p in b['people']]
print(json.dumps(dict(schema_version=1,job_id=b['job_id'],candidate_sha256=b['candidate_sha256'],reviewer_id='Fixture-subprocess',reviewed_at=stamp,coverage=dict(complete=True,enumerated_profile_urls=b['expected_primary_profile_urls'],checked_list_ids=[i['id'] for i in b['lists']]),records=records,sources=sources,findings=[])))
'''
        store.atomic_json(self.root/'audit-config.json',dict(runner=dict(kind='command',command=[sys.executable,'-c',program],timeout_seconds=5)))
        candidate,_,path=self.observe();state=store.read(audit.state_path(self.root,candidate))
        self.assertEqual(state['status'],'reviewed')
        bundle=store.load_ref(self.root,state['result'])
        self.assertEqual(bundle['receipt']['transport'],'command')
        self.assertEqual(bundle['receipt']['run_id'],state['run_id'])
        review=store.read(path);review.update(reviewer='Collector',rationale='Reconciled actual test subprocess result',crosschecks_reviewed=True)
        store.atomic_json(path,review)
        self.assertEqual(store.summarize(store.load_ref(self.root,refresh.accept_review(self.root,path)))['headcount'],1)

    def test_runner_failure_timeout_or_malformed_output_retains_accepted_data(self):
        cases=[subprocess.CompletedProcess([],2,stdout='',stderr='private diagnostic must not be retained'),
            subprocess.CompletedProcess([],0,stdout='invalid json',stderr=''),subprocess.TimeoutExpired('agent',1)]
        store.atomic_json(self.root/'audit-config.json',dict(runner=dict(kind='command',command=['fixture-agent'])))
        for case in cases:
            kwargs={'side_effect':case} if isinstance(case,Exception) else {'return_value':case}
            with patch.object(audit.subprocess,'run',**kwargs):candidate,_,path=self.observe()
            state=store.read(audit.state_path(self.root,candidate))
            self.assertEqual(state['status'],'failed')
            self.assertNotIn('private diagnostic',json.dumps(state))
            self.assertEqual((self.root/'accepted.json').read_bytes(),self.original)

    def test_codex_runner_is_fresh_read_only_and_requires_structured_output(self):
        store.atomic_json(self.root/'audit-config.json',dict(runner=dict(kind='codex',model='gpt-6.1-terra')))
        with patch.object(audit.shutil,'which',return_value='/test/codex'),patch.object(audit.subprocess,'run',return_value=subprocess.CompletedProcess([],1,stdout='',stderr='')) as run:
            self.observe()
        command=run.call_args.args[0];options=run.call_args.kwargs
        self.assertEqual(command[:3],['/test/codex','exec','--ephemeral'])
        self.assertIn('--output-schema',command);self.assertIn('--output-last-message',command)
        self.assertEqual(command[command.index('--sandbox')+1],'read-only')
        self.assertEqual(command[command.index('--model')+1],'gpt-6.1-terra')
        self.assertNotEqual(options['cwd'],str(ROOT))
        self.assertFalse(options.get('shell',False))

    def test_projection_handles_json_without_html_recursion(self):
        nested = '{"content":{"rendered":"' + ('<div>'*1500) + 'ok"}}'
        proj = refresh.projection(nested.encode(), 'https://example.edu/wp-json/wp/v2/profile')
        self.assertEqual(proj['facts']['format'], 'json')
        self.assertTrue(proj['facts']['text_not_extracted'])

    def test_observe_directory_only_scopes_entries_to_directory_url(self):
        cfg = {**self.settings, 'directory_only': True}
        schools = store.read(self.root/'schools.json')['schools']
        schools['example-dir'] = cfg
        store.atomic_json(self.root/'schools.json', dict(schools=schools))
        seen = []
        def fetch(url):
            seen.append(url)
            return dict(url=url, request={'method': 'GET', 'form': {}}, body=directory(), status=200, observed_at='2026-11-22T23:00:00+00:00')
        _, snapshot, _ = refresh.observe(self.root, 'example-dir', '2026-11-22', fetch=fetch, workers=1)
        self.assertFalse(snapshot['failures'])
        self.assertEqual(seen, [self.url])
        self.assertEqual(snapshot['people'][0]['profile_urls'], [self.url])
        self.assertEqual(snapshot['people'][0]['profile_kind'], 'official_directory_entry')


if __name__=='__main__':unittest.main()
