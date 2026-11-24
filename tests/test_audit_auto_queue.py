import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipeline"))
import adjudication  # noqa: E402
import audit_auto_queue as q  # noqa: E402


class AuditAutoQueueTests(unittest.TestCase):
    def test_next_skips_reviewed_and_advances_after_apply(self):
        by_id = {
            "https://openalex.org/I1": {
                "id": "https://openalex.org/I1",
                "display_name": "Alpha University",
                "type": "education",
                "country_code": "US",
                "lineage": ["https://openalex.org/I1"],
                "acronyms": [],
                "alternatives": [],
            },
            "https://openalex.org/I2": {
                "id": "https://openalex.org/I2",
                "display_name": "Beta Institute of Technology",
                "type": "education",
                "country_code": "GB",
                "lineage": ["https://openalex.org/I2"],
                "acronyms": ["BIT"],
                "alternatives": [],
            },
        }
        rows = [
            {
                "raw_affiliation": "Alpha University",
                "status": "auto",
                "institution_id": "https://openalex.org/I1",
                "institution_name": "Alpha University",
                "institution_type": "education",
                "country_code": "US",
                "lineage": "https://openalex.org/I1",
                "score": "1.0",
                "matched_via": "Alpha University",
                "candidate": "Alpha University",
            },
            {
                "raw_affiliation": "Some Random Lab, Boston",
                "status": "auto",
                "institution_id": "https://openalex.org/I1",
                "institution_name": "Alpha University",
                "institution_type": "education",
                "country_code": "US",
                "lineage": "https://openalex.org/I1",
                "score": "0.80",
                "matched_via": "Boston",
                "candidate": "Alpha University",
            },
            {
                "raw_affiliation": "BIT Lab, London, UK",
                "status": "auto",
                "institution_id": "https://openalex.org/I1",
                "institution_name": "Alpha University",
                "institution_type": "education",
                "country_code": "US",
                "lineage": "https://openalex.org/I1",
                "score": "0.75",
                "matched_via": "Lab",
                "candidate": "Alpha University",
            },
            {
                "raw_affiliation": "Already Adjudicated Row",
                "status": "manual",
                "institution_id": "https://openalex.org/I1",
                "institution_name": "Alpha University",
                "institution_type": "education",
                "country_code": "US",
                "lineage": "https://openalex.org/I1",
                "score": "0.75",
                "matched_via": "adjudicated:supported",
                "candidate": "Alpha University",
            },
        ]
        share = {
            "Alpha University": 50.0,
            "Some Random Lab, Boston": 5.0,
            "BIT Lab, London, UK": 12.0,
            "Already Adjudicated Row": 99.0,
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            map_csv = tmp_path / "map.csv"
            ledger = tmp_path / "ledger.jsonl"
            out1 = tmp_path / "batch1.json"
            out2 = tmp_path / "batch2.json"

            fieldnames = list(rows[0].keys())
            adjudication.write_map(fieldnames, rows, path=map_csv)

            with (
                mock.patch.object(adjudication, "MAP_CSV", map_csv),
                mock.patch.object(adjudication, "LEDGER", ledger),
                mock.patch.object(adjudication, "load_index", return_value=by_id),
                mock.patch.object(adjudication, "string_weights", return_value=({}, share)),
            ):
                q.main(["next", "--scope", "auto-no-ev", "--credited-only", "--limit", "1", "--out", str(out1)])
                b1 = json.loads(out1.read_text())
                self.assertEqual(b1["remaining_in_scope"], 2)
                self.assertEqual(b1["batch_size"], 1)
                self.assertEqual(b1["rows"][0]["raw_affiliation"], "BIT Lab, London, UK")
                self.assertTrue(b1["rows"][0]["candidates"])

                # Apply decision for the first item and re-run next (restart simulation)
                _, cur_rows, _ = adjudication.read_map(map_csv)
                acc, rej = adjudication.merge(
                    cur_rows,
                    fieldnames,
                    [
                        {
                            "raw_affiliation": "BIT Lab, London, UK",
                            "decision": "corrected",
                            "institution_id": "https://openalex.org/I2",
                            "evidence": "BIT in London, UK is Beta Institute of Technology.",
                            "decided_by": "test",
                        }
                    ],
                    by_id,
                )
                self.assertEqual(len(acc), 1)
                self.assertEqual(len(rej), 0)
                adjudication.write_map(fieldnames, cur_rows, path=map_csv)

                q.main(["next", "--scope", "auto-no-ev", "--credited-only", "--limit", "5", "--out", str(out2)])
                b2 = json.loads(out2.read_text())
                self.assertEqual(b2["remaining_in_scope"], 1)
                self.assertEqual(b2["rows"][0]["raw_affiliation"], "Some Random Lab, Boston")


if __name__ == "__main__":
    unittest.main()
