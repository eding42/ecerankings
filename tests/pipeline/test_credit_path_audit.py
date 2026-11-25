import unittest
from pipeline.audit_credit_paths import publisher_evidence


class CreditPathEvidenceTest(unittest.TestCase):
    def test_position_name_and_count_must_match_before_attaching_evidence(self):
        item = {'author_index': 0, 'author_count': 2, 'author_name': 'Alice Jones'}
        authors = [{'given': 'Alice', 'family': 'Jones', 'affiliation': [{'name': 'Example University'}]},
                   {'given': 'Bob', 'family': 'Smith'}]
        self.assertEqual(publisher_evidence(item, {'author': authors})['raw_affiliations'], ['Example University'])
        for altered in [authors[::-1], authors[:1], [authors[0], authors[0]]]:
            self.assertEqual(publisher_evidence(item, {'author': altered})['status'], 'byline_mismatch')

    def test_missing_affiliations_are_not_evidence_of_no_affiliation(self):
        item = {'author_index': 0, 'author_count': 1, 'author_name': 'Alice Jones'}
        self.assertEqual(publisher_evidence(item, {'author': [{'given': 'Alice', 'family': 'Jones'}]})['status'], 'no_affiliations')


if __name__ == '__main__':
    unittest.main()
