import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from faculty_registry import classify_role, validate_people
from faculty_pilot import sha
from package_site import faculty_files


class FacultyRegistryTests(unittest.TestCase):
    def setUp(self):
        self.policy=json.loads((ROOT/'data/faculty/policy.json').read_text())
        people=json.loads((ROOT/'data/faculty/people.json').read_text())['people']
        self.person=copy.deepcopy(next(p for p in people if p['appointments'][0]['decision']['status']=='included'))
        for appointment in self.person['appointments']:appointment['decision']['policy_id']=self.policy['id']
        self.sources={s['id']:s for s in json.loads((ROOT/'data/faculty/sources.json').read_text())['sources']}

    def errors(self):
        return validate_people([self.person],self.policy,self.sources)

    def test_disambiguates_excluded_professor_titles(self):
        for title,category in [('Professor of the Practice','teaching'),('Professor (Research)','research_only'),('Professor, by courtesy','courtesy'),('Adjunct Professor','adjunct'),('Professor Emeritus','emeritus'),('Professor in Residence','in_residence')]:
            with self.subTest(title=title):self.assertEqual(classify_role(title),category)

    def test_courtesy_and_joint_secondary_qualify_but_cs_only_does_not(self):
        self.assertEqual(self.errors(),[])
        self.person['appointments'][0]['membership']='cs_only'
        self.assertTrue(any('ineligible appointment' in e for e in self.errors()))
        self.person['appointments'][0]['membership']='ece'
        for category in ['courtesy','joint_secondary']:
            self.person['appointments'][0]['category']=category
            self.assertEqual(self.errors(),[])
        for category in ['adjunct','affiliate','teaching','research_only','emeritus']:
            self.person['appointments'][0]['category']=category
            self.assertTrue(any('ineligible appointment' in e for e in self.errors()))

    def test_personal_site_cannot_replace_official_membership(self):
        for c in self.person['claims']:
            if c['property']=='department_membership':c['source_ids']=['personal']
        self.sources['personal']={'kind':'university_linked_personal'}
        self.assertTrue(any('official EE/ECE' in e for e in self.errors()))

    def test_announced_incoming_professor_is_included_with_future_status_and_date(self):
        people=json.loads((ROOT/'data/faculty/people.json').read_text())['people']
        self.person=copy.deepcopy(next(p for p in people if p['display_name']=='Qian Xu'))
        appointment=self.person['appointments'][0]
        appointment['decision']['policy_id']=self.policy['id']
        self.assertEqual(appointment['decision']['status'],'included')
        self.assertEqual(appointment['current_state'],'incoming')
        self.assertEqual(appointment['effective_from']['year'],2027)
        self.assertEqual(self.errors(),[])
        self.person['claims']=[c for c in self.person['claims'] if c['property']!='appointment_state']
        self.assertTrue(any('incoming appointment lacks' in e for e in self.errors()))

    def test_incoming_courtesy_requires_announcement_and_does_not_override_other_exclusions(self):
        appointment=self.person['appointments'][0]
        appointment['current_state']='incoming'
        appointment['category']='courtesy'
        self.assertTrue(any('incoming appointment lacks' in e for e in self.errors()))
        self.person['claims'].append(dict(property='appointment_state',value='incoming',state='supported',source_ids=appointment['decision']['source_ids']))
        self.assertEqual(self.errors(),[])
        for category,membership in [('adjunct','ece'),('regular','cs_only')]:
            appointment['category']=category;appointment['membership']=membership
            self.assertTrue(any('ineligible appointment' in e for e in self.errors()))

    def test_cs_only_regular_professor_is_retained_as_an_exclusion(self):
        appointment=self.person['appointments'][0]
        appointment['membership']='cs_only'
        appointment['decision']['status']='excluded'
        appointment['current_state']='not_in_core'
        self.assertEqual(self.errors(),[])

    def test_missing_claim_evidence_and_duplicate_identity_fail(self):
        self.person['claims'][0]['source_ids']=[]
        self.assertTrue(any('claim lacks' in e for e in self.errors()))
        self.assertTrue(any('Duplicate local person' in e for e in validate_people([self.person,self.person],self.policy,self.sources)))

    def test_packager_refuses_modified_or_unresolved_faculty_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            site=Path(tmp);folder=site/'faculty';folder.mkdir()
            payload={'schema_version':1,'field':'ece','policy_id':self.policy['id'],'metric_id':'ece_affiliated_faculty','schools':[{'institution_id':'https://openalex.org/I1','headcount':12,'observed_on':'2026-11-22','policy_id':self.policy['id'],'roster_url':'https://university.edu/faculty'}]}
            def save():
                (folder/'current.json').write_text(json.dumps(payload))
                (folder/'manifest.json').write_text(json.dumps({'field':'ece','policy_id':self.policy['id'],'metric_id':payload['metric_id'],'validation':{'status':'passed'},'artifacts':{'current.json':{'sha256':sha((folder/'current.json').read_bytes())}}}))
            save()
            self.assertEqual(len(faculty_files(site)),2)
            payload['metric_id']='ece_regular_faculty';save()
            with self.assertRaisesRegex(ValueError,'metric/policy'):faculty_files(site)
            payload['metric_id']='ece_affiliated_faculty';save()
            (folder/'current.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):faculty_files(site)
            payload['schools'][0]['headcount']=None;save()
            with self.assertRaisesRegex(ValueError,'Unresolved faculty'):faculty_files(site)
            payload['schools'][0].update(headcount=12,incoming_headcount=13,current_headcount=0);save()
            with self.assertRaisesRegex(ValueError,'count breakdown'):faculty_files(site)


if __name__=='__main__':unittest.main()
