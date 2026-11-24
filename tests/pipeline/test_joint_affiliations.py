"""A status=joint map row credits every member university; the author's share is split evenly."""

import unittest

from pipeline import aggregate

JOINT = {
    "status": "joint",
    "institution_id": "https://openalex.org/I1|https://openalex.org/I2",
    "institution_name": "Zhejiang University | University of Illinois Urbana-Champaign",
    "institution_type": "education",
}


class JointAffiliations(unittest.TestCase):
    def test_raw_dict_and_prepared_map_resolve_to_every_member(self):
        for affil_map in ({"ZJU-UIUC Institute": JOINT}, aggregate.prepare_affiliation_map({"ZJU-UIUC Institute": JOINT})):
            resolved = aggregate.resolve_raw_affiliations(["ZJU-UIUC Institute"], affil_map)
            self.assertEqual([r["id"] for r in resolved], ["https://openalex.org/I1", "https://openalex.org/I2"])
            self.assertEqual([r["display_name"] for r in resolved],
                             ["Zhejiang University", "University of Illinois Urbana-Champaign"])

    def test_author_credit_set_has_both_universities_so_share_splits(self):
        affil_map = aggregate.prepare_affiliation_map({"ZJU-UIUC Institute": JOINT})
        unique, used_map = aggregate.resolve_authorship(
            {"raw_affiliations": ["ZJU-UIUC Institute"]}, affil_map, {}, {"education"})
        self.assertTrue(used_map)
        self.assertEqual(sorted(unique), ["https://openalex.org/I1", "https://openalex.org/I2"])

    def test_native_openalex_institutions_still_win_over_the_map(self):
        affil_map = aggregate.prepare_affiliation_map({"ZJU-UIUC Institute": JOINT})
        native = {"institutions": [{"id": "https://openalex.org/I9", "display_name": "Native U", "type": "education"}],
                  "raw_affiliations": ["ZJU-UIUC Institute"]}
        unique, used_map = aggregate.resolve_authorship(native, affil_map, {}, {"education"})
        self.assertFalse(used_map)
        self.assertEqual(list(unique), ["https://openalex.org/I9"])

    def test_joint_row_with_a_non_credit_type_credits_nothing(self):
        affil_map = aggregate.prepare_affiliation_map({"x": dict(JOINT, institution_type="company")})
        unique, _ = aggregate.resolve_authorship({"raw_affiliations": ["x"]}, affil_map, {}, {"education"})
        self.assertEqual(unique, {})


if __name__ == "__main__":
    unittest.main()
