import copy
import unittest
from pipeline.apply_authorship_corrections import correct
from pipeline.adjudication import supplement_index


class AuthorshipCorrectionTest(unittest.TestCase):
    def setUp(self):
        self.index = {'I2': {'id': 'I2', 'display_name': 'University Two', 'type': 'education', 'country_code': 'US', 'lineage': ['I2']}}
        self.work = {'doi': 'https://doi.org/10.1/x', 'authorships': [{'author_name': 'Alice', 'institutions': [{'id': 'I1'}]}, {'author_name': 'Bob'}]}
        self.decision = {'doi': '10.1/x', 'author_names': ['Alice', 'Bob'], 'author_index': 0, 'source_url': 'https://publisher.example/paper', 'evidence': 'Printed author block', 'raw_affiliations': ['University Two'], 'expected_institution_ids': ['I1'], 'institution_ids': ['I2']}

    def test_native_correction_is_evidenced_replayable_and_does_not_shift_authors(self):
        result, changed = correct(self.work, self.decision, self.index)
        self.assertTrue(changed)
        self.assertEqual(self.work['authorships'][0]['institutions'], [{'id': 'I1'}])
        self.assertEqual(result['authorships'][1], self.work['authorships'][1])
        self.assertEqual(result['authorships'][0]['affiliation_correction']['prior_institutions'], [{'id': 'I1'}])
        replayed, changed = correct(result, self.decision, self.index)
        self.assertFalse(changed)
        self.assertEqual(replayed, result)

    def test_changed_identity_or_prior_evidence_requires_new_review(self):
        variants = [{'author_names': ['Bob', 'Alice']}, {'expected_institution_ids': ['I9']}, {'source_url': ''}, {'author_index': 9}]
        for delta in variants:
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                correct(self.work, dict(self.decision, **delta), self.index)

    def test_a_paper_without_a_doi_matches_only_its_exact_record_id(self):
        work = {'id': 'abc', 'doi': None, 'authorships': self.work['authorships']}
        decision = dict(self.decision, doi=None, work_id='abc')
        self.assertTrue(correct(work, decision, self.index)[1])
        for bad in (dict(decision, work_id='abd'), dict(decision, work_id=None), self.decision):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                correct(work, bad, self.index)
        # A record that has a DOI must be identified by it.
        with self.assertRaises(ValueError):
            correct(dict(work, doi='10.1/y'), decision, self.index)

    def test_supplement_requires_evidence_and_never_overwrites_known_identity(self):
        iid = 'https://openalex.org/I2'
        record = {'name': 'University Two', 'country': 'US', 'type': 'education', 'source_url': 'https://example.edu', 'evidence': 'Exact API institution record'}
        self.assertEqual(supplement_index({}, {iid: record})[iid]['display_name'], 'University Two')
        with self.assertRaises(ValueError):
            supplement_index({}, {iid: dict(record, evidence='')})
        self.assertEqual(supplement_index({iid: {'display_name': 'Existing'}}, {iid: record})[iid]['display_name'], 'Existing')
