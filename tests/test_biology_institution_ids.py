import csv
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'pipeline'))
import aggregate_biosciences as bio  # noqa: E402

# Copied from the OpenAlex institution records, never from memory. Before adding
# an ID, open https://api.openalex.org/institutions/<id> and copy display_name.
# Check the record's country too: names repeat across countries.
OPENALEX_NAMES = {
    'I205783295': 'Cornell University',
    'I4387153466': 'Weill Cornell Medicine',
    'I24943067': 'Fudan University',
    'I133868755': 'Shanghai Medical College of Fudan University',
    'I592451': 'Indiana University',
    'I4394709130': 'Indiana University School of Medicine',
    'I102322142': 'Rutgers, The State University of New Jersey',
    'I4402554120': 'Rutgers New Jersey Medical School',
    'I91045830': 'Texas A&M University',
    'I125029298': 'Texas A&M Health Science Center',
    'I139290212': 'Hofstra University',
    'I4210106353': 'Donald & Barbara Zucker School of Medicine at Hofstra/Northwell',
    'I44265643': 'Rowan University',
    'I4210089330': 'Cooper Medical School of Rowan University',
    'I164861460': 'Manipal Academy of Higher Education',
    'I76414455': 'Kasturba Medical College, Manipal',
    'I4387153400': 'Kasturba Medical College, Mangalore',
    'I91357014': 'Banaras Hindu University',
    'I51317819': 'Institute of Medical Sciences',
    'I3019271933': 'Nicolaus Copernicus University',
    'I4210148386': 'Collegium Medicum in Bydgoszcz',
    'I63596082': 'Tunis El Manar University',
    'I4403386600': 'Faculté de médecine de Tunis',
    'I169521973': 'University of New Mexico',
    'I4405255059': 'University of New Mexico Health Sciences Center',
    'I180726961': 'Shenzhen University',
    'I4210145292': 'Shenzhen University Health Science Center',
    'I32574673': 'Shantou University',
    'I4210120522': 'Shantou University Medical College',
    'I138006243': 'University of Arizona',
    'I4405259572': 'University of Arizona College of Medicine- Phoenix',
    'I126744593': 'University of Maryland, Baltimore',
    'I4405257352': 'University of Maryland School of Medicine',
    'I33213144': 'University of Florida',
    'I61515104': 'University of Florida Health Science Center',
    'I150149174': 'Mercer University',
    'I2801518522': 'Mercer University Health Sciences Center',
    'I867280407': 'The University of Texas Southwestern Medical Center',
    'I1343551460': 'The University of Texas MD Anderson Cancer Center',
    'I1334819555': 'Memorial Sloan Kettering Cancer Center',
    'I123431417': 'Scripps Research Institute',
}


def url(openalex_id):
    return f'https://openalex.org/{openalex_id}'


def institution(openalex_id, kind='education', country='US'):
    return {'id': url(openalex_id), 'display_name': OPENALEX_NAMES.get(openalex_id, openalex_id),
            'type': kind, 'country_code': country}


def credited(*institutions):
    targets = bio.resolve_authorship({'institutions': list(institutions)})
    return {key: value['name'] for key, value in targets.items()}


class BiologyInstitutionIdTests(unittest.TestCase):
    def test_every_id_carries_its_openalex_name(self):
        for university, university_name, schools in bio.MEDICAL_SCHOOLS:
            for openalex_id, claimed in ((university, university_name), *schools):
                with self.subTest(openalex_id):
                    self.assertEqual(claimed, OPENALEX_NAMES.get(openalex_id))
        for key, claimed in bio.ACADEMIC_ALLOWLIST.items():
            with self.subTest(key):
                self.assertEqual(claimed, OPENALEX_NAMES.get(key.rsplit('/', 1)[-1]))

    def test_each_school_is_merged_once_and_no_target_is_merged_away(self):
        schools = [school for _, _, listed in bio.MEDICAL_SCHOOLS for school, _ in listed]
        self.assertEqual(len(schools), len(set(schools)))
        self.assertFalse(set(bio.INSTITUTION_ROLLUP) & set(bio.INSTITUTION_ROLLUP.values()))


class BiologyCreditTests(unittest.TestCase):
    def test_medical_school_counts_once_toward_its_university(self):
        expected = {url('I205783295'): 'Cornell University'}
        self.assertEqual(credited(institution('I4387153466')), expected)
        self.assertEqual(credited(institution('I4387153466'), institution('I205783295')), expected)

    def test_hospital_alone_credits_nobody(self):
        # Massachusetts General Hospital and Stanford Medicine
        for hospital in ('I4210087915', 'I4210137306'):
            self.assertEqual(credited(institution(hospital, kind='healthcare')), {})

    def test_university_named_beside_a_hospital_keeps_full_credit(self):
        self.assertEqual(
            credited(institution('I4210087915', kind='healthcare'), institution('I136199984')),
            {url('I136199984'): 'I136199984'})

    def test_merged_university_outside_the_us_keeps_its_country(self):
        work = {'id': 'w1', 'title': 'A study', 'type': 'article', 'authorships': [
            {'institutions': [institution('I133868755', country='CN')]}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'data').mkdir()
            (root / 'data/institutions.json').write_text('{"by_id": {}}')
            (root / 'cache/venue/2024').mkdir(parents=True)
            (root / 'cache/venue/2024/works.jsonl').write_text(json.dumps(work) + '\n')
            (root / 'areas.json').write_text(json.dumps({'areas': {'area': {'venues': [{'key': 'venue'}]}}}))
            with mock.patch.object(bio, 'REPO_ROOT', tmp), mock.patch('builtins.print'):
                bio.run_aggregation(str(root / 'cache'), str(root / 'areas.json'), str(root / 'out'))
            with open(root / 'out/inst-area-year_edu_only.csv', newline='') as handle:
                rows = [(r['institution_name'], r['country']) for r in csv.DictReader(handle)]
        self.assertEqual(rows, [('Fudan University', 'CN')])


if __name__ == '__main__':
    unittest.main()
