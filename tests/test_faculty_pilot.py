"""Protect the evidence boundaries needed for faculty enrichment."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from verify_faculty_pilot import check_match


class AcceptedAuthorshipTests(unittest.TestCase):
    def setUp(self):
        self.work = {'doi':'https://doi.org/10.1234/example', 'authorships':[
            {'author_name':'Student One','author_id':'crossref:name:student-one','institutions':[]},
            {'author_name':'Jane Doe','author_id':None,'institutions':[{'id':'I1'}]},
        ]}
        self.match = {'status':'accepted','person_id':'person:1','doi':'10.1234/example',
                      'evidence_source_key':'official-publications','byline_position':1,
                      'author_name':'Jane Doe','author_id':None,'author_count':2,'institution_ids':['I1']}
        self.anchors = {('person:1','10.1234/example','official-publications')}
        self.publisher = {'doi':'10.1234/example','authors':[
            {'given':'Student','family':'One'}, {'given':'Jane','family':'Doe'}]}

    def test_missing_vendor_id_can_be_resolved_with_paper_evidence(self):
        check_match(self.match,self.work,self.anchors,self.publisher)

    def test_a_shared_author_cluster_does_not_replace_person_specific_evidence(self):
        with self.assertRaisesRegex(ValueError,'person-specific'):
            check_match(self.match,self.work,{('somebody-else','10.1234/example','official-publications')},self.publisher)

    def test_wrong_byline_slot_is_rejected(self):
        bad=copy.deepcopy(self.match); bad['byline_position']=0
        with self.assertRaisesRegex(ValueError,'Wrong cached author'):
            check_match(bad,self.work,self.anchors,self.publisher)

    def test_current_employer_cannot_replace_publication_institution(self):
        bad=copy.deepcopy(self.match); bad['institution_ids']=['new-employer']
        with self.assertRaisesRegex(ValueError,'institutions were changed'):
            check_match(bad,self.work,self.anchors,self.publisher)

    def test_publisher_byline_disagreement_is_not_accepted(self):
        bad=copy.deepcopy(self.publisher); bad['authors'][1]['given']='John'
        with self.assertRaisesRegex(ValueError,'different author'):
            check_match(self.match,self.work,self.anchors,bad)

    def test_truncated_cached_byline_is_rejected(self):
        bad=copy.deepcopy(self.publisher); bad['authors'].append({'given':'Missing','family':'Person'})
        with self.assertRaisesRegex(ValueError,'author counts differ'):
            check_match(self.match,self.work,self.anchors,bad)

    def test_same_title_or_identifier_does_not_override_different_work(self):
        bad=copy.deepcopy(self.work); bad['doi']='10.1234/different-edition'
        with self.assertRaisesRegex(ValueError,'Work DOI differs'):
            check_match(self.match,bad,self.anchors,self.publisher)


if __name__=='__main__': unittest.main()
