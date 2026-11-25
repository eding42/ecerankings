import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'pipeline'))
import aggregate_biosciences as bio  # noqa: E402

# Copied from the OpenAlex institution records, never from memory. Before adding
# an ID, open https://api.openalex.org/institutions/<id> and copy display_name.
OPENALEX_NAMES = {
    'I136199984': 'Harvard University',
    'I97018004': 'Stanford University',
    'I145311948': 'Johns Hopkins University',
    'I4210087915': 'Massachusetts General Hospital',
    'I1283280774': "Brigham and Women's Hospital",
    'I4210117453': 'Dana-Farber Cancer Institute',
    'I1288882113': "Boston Children's Hospital",
    'I48633490': 'Mass General Brigham',
    'I4210137306': 'Stanford Medicine',
    'I2799853436': 'Johns Hopkins Medicine',
    'I867280407': 'The University of Texas Southwestern Medical Center',
    'I1343551460': 'The University of Texas MD Anderson Cancer Center',
    'I1334819555': 'Memorial Sloan Kettering Cancer Center',
    'I123431417': 'Scripps Research Institute',
}

# Each approved rollup, by name: a hospital and the university it credits.
ROLLUPS = {
    ('Massachusetts General Hospital', 'Harvard University'),
    ("Brigham and Women's Hospital", 'Harvard University'),
    ('Dana-Farber Cancer Institute', 'Harvard University'),
    ("Boston Children's Hospital", 'Harvard University'),
    ('Mass General Brigham', 'Harvard University'),
    ('Stanford Medicine', 'Stanford University'),
    ('Johns Hopkins Medicine', 'Johns Hopkins University'),
}


def name(openalex_id):
    short = openalex_id.rsplit('/', 1)[-1]
    return OPENALEX_NAMES.get(short, f'unverified ID {short}')


def words(text):
    return re.findall(r'\w+', text.lower())


class BiologyInstitutionIdTests(unittest.TestCase):
    def test_rollups_join_the_intended_institutions(self):
        self.assertEqual({(name(s), name(t)) for s, t in bio.INSTITUTION_ROLLUP.items()}, ROLLUPS)

    def test_display_names_match_their_ids(self):
        for table in (bio.CANONICAL_NAMES, bio.ACADEMIC_ALLOWLIST):
            for openalex_id, claimed in table.items():
                with self.subTest(openalex_id):
                    self.assertEqual(words(claimed), words(name(openalex_id)))


if __name__ == '__main__':
    unittest.main()
