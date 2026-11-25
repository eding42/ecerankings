import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
import faculty_capture as capture


class CaptureTests(unittest.TestCase):
    def test_replays_pinned_capture_as_browser_dom_without_status_or_origin_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'a.json').write_text(json.dumps({'people': []}))
            (folder / 'manifest.json').write_text(json.dumps(dict(tool='fixture browser', captures={
                'https://x.edu/people/': dict(file='a.json', observed_at='2026-11-25T08:00:00+00:00')})))
            fetch = capture.make_fetch(capture.load(folder))
            result = fetch('https://x.edu/people')
            self.assertEqual(result['capture_format'], 'browser_dom')
            self.assertIsNone(result['status'])
            self.assertEqual(result['capture_tool'], 'fixture browser')
            self.assertIn('error', fetch('https://x.edu/other'))


if __name__ == '__main__':
    unittest.main()
