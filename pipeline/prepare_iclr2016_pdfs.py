#!/usr/bin/env python3
"""Restore hash-pinned ICLR 2016 conference PDFs into an isolated ML stage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / 'data/refresh/iclr-2016-pdf-sources.jsonl'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-root', type=Path, required=True)
    args = parser.parse_args()
    out = args.stage_root / 'pdf/iclr/2016'
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in SOURCES.read_text(encoding='utf8').splitlines() if line.strip()]
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('duplicate paper identifiers in PDF source manifest')
    for row in rows:
        ident, expected = row['id'], row['sha256']
        if not all(c.isdigit() or c == '.' for c in ident) or len(expected) != 64:
            raise ValueError('invalid source identifier or hash')
        target = out / (ident + '.pdf')
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        req = urllib.request.Request(row['url'], headers={'User-Agent': 'ECERankings/1.0 (mailto:eding2019@gmail.com)'})
        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read()
        if not body.startswith(b'%PDF') or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('PDF hash mismatch for ' + ident)
        tmp = target.with_suffix('.part')
        tmp.write_bytes(body)
        os.replace(tmp, target)
    print(f'{len(rows)} hash-verified conference PDFs in {out}; other papers remain unresolved')

if __name__ == '__main__':
    main()
