#!/usr/bin/env python3
"""Draw credited authorships and fetch independent publisher affiliation evidence.

Read-only: sealed.json records production resolver targets; blind.json contains
only identities and publisher evidence. Missing evidence is not a verdict.
"""
import argparse
import hashlib
import heapq
import json
from pathlib import Path
import re
import unicodedata
import urllib.parse
import urllib.request
import time

try:
    from . import aggregate
    from .workkey import work_key, record_key, norm_doi
except ImportError:
    import aggregate
    from workkey import work_key, record_key, norm_doi


def name_key(name):
    text = unicodedata.normalize('NFKD', name or '')
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in text if not unicodedata.combining(c)).lower())


def publisher_evidence(item, reference):
    """Attach affiliations only after a unique full-name match at the same slot."""
    authors = reference.get('author') or []
    i = item['author_index']
    names = [name_key(' '.join(filter(None, [a.get('given'), a.get('family') or a.get('name')]))) for a in authors]
    expected = name_key(item['author_name'])
    if not expected or len(authors) != item['author_count'] or i >= len(authors) or names[i] != expected or names.count(expected) != 1:
        return {'status': 'byline_mismatch', 'publisher_names': names}
    raw = [a.get('name') for a in authors[i].get('affiliation') or [] if a.get('name')]
    return {'status': 'evidence' if raw else 'no_affiliations', 'raw_affiliations': raw}


def draw(cache, registry, seed, size):
    mapping = aggregate.prepare_affiliation_map(aggregate.load_affiliation_map())
    aliases = aggregate.canonical_aliases(aggregate.load_aliases())
    excluded = aggregate.load_exclusions()
    selected = []
    counter = 0
    for area in registry['areas'].values():
        for venue in area['venues']:
            seen = set()
            venue_excluded = excluded | {'doi:' + norm_doi(doi) for doi in venue.get('exclude_dois', [])}
            for path in sorted((cache / venue['key']).glob('*/works.jsonl')):
                year = int(path.parent.name)
                for line in path.open():
                    work = json.loads(line)
                    key = record_key(work, venue['key'], year)
                    if key in seen:
                        continue
                    seen.add(key)
                    if not work.get('doi') or work_key(work, venue['key'], year) in venue_excluded or (work.get('type') or '').lower() in aggregate.NONRESEARCH_TYPES:
                        continue
                    authors = work.get('authorships') or []
                    for i, author in enumerate(authors):
                        targets, used_map = aggregate.resolve_authorship(author, mapping, aliases, {'education'})
                        if not targets:
                            continue
                        identity = f'{venue["key"]}|{year}|{key}|{i}'
                        score = int(hashlib.sha256(f'{seed}|{identity}'.encode()).hexdigest(), 16)
                        item = {'key': identity, 'venue': venue['key'], 'year': year, 'doi': work['doi'],
                                'title': work.get('title'), 'author_index': i, 'author_count': len(authors),
                                'author_name': author.get('author_name'), 'cached_author': author,
                                'resolution_path': 'map' if used_map else 'native',
                                'credited_targets': sorted(targets), 'credit_per_target': 1 / len(authors) / len(targets)}
                        counter += 1
                        if len(selected) < size:
                            heapq.heappush(selected, (-score, counter, item))
                        elif score < -selected[0][0]:
                            heapq.heapreplace(selected, (-score, counter, item))
    return [r[2] for r in sorted(selected, reverse=True)], counter


def fetch(item):
    doi = item['doi'].removeprefix('https://doi.org/').removeprefix('http://doi.org/')
    url = 'https://api.crossref.org/works/' + urllib.parse.quote(doi, safe='/') + '?mailto=erding%40usc.edu'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ECERankings affiliation audit (https://ecerankings.org)'})
        with urllib.request.urlopen(req, timeout=35) as response:
            reference = json.load(response)['message']
        return dict(item, publisher_source=url, publisher=publisher_evidence(item, reference))
    except Exception as exc:
        return dict(item, publisher_source=url, publisher={'status': 'fetch_error', 'error': str(exc)[:200]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--size', type=int, default=50)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--retry-errors', action='store_true', help='retry failed publisher requests from this saved draw')
    args = parser.parse_args()
    if (args.out.exists() and not args.retry_errors) or args.size < 1:
        parser.error('output must be new; size must be positive')
    inputs = [aggregate.AREAS_JSON, aggregate.MAP_CSV, aggregate.EXCLUDED_CSV,
              aggregate.METADATA_CORRECTIONS, str(Path(aggregate.REPO_ROOT) / 'data/institution-aliases.csv')]
    hashes = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in inputs}
    registry = json.loads(Path(aggregate.AREAS_JSON).read_text())
    if args.retry_errors:
        saved = json.loads((args.out / 'draw.json').read_text())
        if saved['input_hashes'] != hashes or saved['seed'] != args.seed:
            raise ValueError('Saved audit input hashes or seed differ')
        population = saved['population_authorships']
        rows = json.loads((args.out / 'sealed.json').read_text())
        for i, item in enumerate(rows):
            if item['publisher']['status'] != 'fetch_error':
                continue
            time.sleep(1)
            rows[i] = fetch(item)
            (args.out / 'sealed.json').write_text(json.dumps(rows, indent=2) + '\n')
    else:
        sample, population = draw(args.cache_dir, registry, args.seed, args.size)
        args.out.mkdir(parents=True)
        (args.out / 'draw.json').write_text(json.dumps({'seed': args.seed, 'input_hashes': hashes, 'population_authorships': population, 'sample': sample}, indent=2) + '\n')
        # Use Crossref's polite pool sequentially; a burst can produce 429s.
        rows = []
        for item in sample:
            rows.append(fetch(item))
            time.sleep(0.25)
    if any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h for p, h in hashes.items()):
        raise ValueError('Attribution inputs changed during audit; preserve the draw and rerun with a fresh seed')
    (args.out / 'sealed.json').write_text(json.dumps(rows, indent=2) + '\n')
    blind = [{k: r[k] for k in ('key', 'title', 'doi', 'author_index', 'author_count', 'author_name', 'publisher_source', 'publisher')} for r in rows]
    (args.out / 'blind.json').write_text(json.dumps(blind, indent=2) + '\n')
    print(json.dumps({'sampled': len(rows), 'population_authorships': population, 'evidence': sum(r['publisher']['status'] == 'evidence' for r in rows)}))


if __name__ == '__main__':
    main()
