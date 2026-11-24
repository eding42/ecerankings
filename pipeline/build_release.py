#!/usr/bin/env python3
"""Build and validate a full candidate release in a separate output directory.

Works the same way for every field (--field ece|biology|earth-space): aggregate,
split, institution metadata, structural validation, and a hashed manifest.
This command never promotes its outputs into a site data directory or deploys them.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import math
import pathlib
import subprocess
import sys

from aggregation_runtime import digest_files, select_executor
from fields import add_field_argument, get_field

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE_RECORDS = 'data/refresh/institution-records-2026-10-28.json'
CODE_FILES = ['pipeline/aggregate.py', 'pipeline/aggregate_biosciences.py',
              'pipeline/aggregation_runtime.py', 'pipeline/fields.py',
              'pipeline/workkey.py', 'pipeline/split.py', 'pipeline/build_release.py',
              'pipeline/verify.py', 'pipeline/promote_release.py']


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def read_csv(path):
    with path.open(newline='') as handle:
        yield from csv.DictReader(handle)


def validate(output, registry):
    """Return measured artifact facts, raising on structural inconsistencies."""
    areas = registry['areas']
    institutions = json.loads((output / 'institutions.json').read_text())
    expected = {}
    expected_rows = {}
    totals = collections.Counter()
    years = set()
    unique = set()
    for row in read_csv(output / 'inst-area-year.csv'):
        key = (row['institution_id'], row['area'], int(row['year']))
        score, count = float(row['adjusted_count']), int(row['pub_count'])
        if key in unique or key[1] not in areas or key[0] not in institutions:
            raise ValueError(f'Duplicate or invalid aggregate key: {key}')
        if not math.isfinite(score) or score < 0 or score > count + 1e-5 or count < 1:
            raise ValueError(f'Invalid credit at {key}: {score}, {count}')
        unique.add(key)
        expected[key] = score
        expected_rows[key] = {'i': row['institution_id'], 'n': row['institution_name'],
                              'y': int(row['year']), 'p': count, 'a': score}
        totals[key[1]] += score
        years.add(key[2])
    venue_sums = collections.Counter()
    venue_rows = collections.Counter()
    venue_expected = collections.defaultdict(dict)
    known_venues = {v['key']: area for area, a in areas.items() for v in a['venues']}
    for row in read_csv(output / 'inst-venue-year.csv'):
        if known_venues.get(row['venue']) != row['area']:
            raise ValueError(f'Invalid venue ownership: {row["venue"]}')
        key = (row['institution_id'], row['area'], int(row['year']))
        score, count = float(row['adjusted_count']), int(row['pub_count'])
        identity = (key[0], key[2])
        table = venue_expected[(key[1], row['venue'])]
        if (identity in table or key[0] not in institutions or not math.isfinite(score)
                or score < 0 or count < 1 or score > count + 1e-5):
            raise ValueError(f'Duplicate or invalid venue aggregate: {key}, {row["venue"]}')
        table[identity] = {'i': key[0], 'n': row['institution_name'], 'y': key[2], 'p': count, 'a': score}
        venue_sums[key] += score
        venue_rows[row['venue']] += 1
    if set(expected) != set(venue_sums):
        raise ValueError('Area and venue tables have different institution/area/year keys')
    for key, score in expected.items():
        if abs(score - venue_sums[key]) > 1e-4:
            raise ValueError(f'Area and venue credit do not reconcile: {key}')
    missing_default_venues = [venue for venue, area in known_venues.items()
                              if areas[area].get('default_on') and not venue_rows[venue]]
    if missing_default_venues:
        raise ValueError('Default-on venues with no credit: ' + ', '.join(missing_default_venues))
    for (area, venue), expected_venue in venue_expected.items():
        records = json.loads((output / area / f'{venue}.json').read_text())
        seen = set()
        for row in records:
            key = (row['i'], row['y'])
            if key in seen or row != expected_venue.get(key):
                raise ValueError(f'Venue JSON differs from CSV: {venue}, {key}')
            seen.add(key)
        if seen != expected_venue.keys():
            raise ValueError(f'Venue JSON is incomplete: {venue}')
    for area in areas:
        records = json.loads((output / f'{area}.json').read_text())
        seen = set()
        for row in records:
            key = (row['i'], area, row['y'])
            if key in seen or key not in expected or row != expected_rows[key]:
                raise ValueError(f'Area JSON differs from CSV: {key}')
            seen.add(key)
        if seen != {key for key in expected if key[1] == area}:
            raise ValueError(f'Area JSON is incomplete: {area}')
        if areas[area].get('default_on') and not records:
            raise ValueError(f'Default-on area has no credited institutions: {area}')
    author_sums = collections.Counter()
    author_rows = collections.Counter()
    has_authors = (output / 'author-info.csv').exists()
    for row in (read_csv(output / 'author-info.csv') if has_authors else ()):
        key = (row['institution_id'], row['area'], int(row['year']))
        value = float(row['adjusted_count'])
        if key not in expected or not math.isfinite(value) or value < 0:
            raise ValueError(f'Invalid author credit: {key}')
        author_sums[key] += value
        author_rows[key] += 1
    if has_authors and set(author_sums) != set(expected):
        raise ValueError('Author and area tables have different keys')
    for key, score in (expected.items() if has_authors else ()):
        # Each CSV cell was independently rounded to five decimals.
        bound = .000005 * (author_rows[key] + 1) + 1e-8
        if abs(author_sums[key] - score) > bound:
            raise ValueError(f'Author and area credit do not reconcile: {key}')
    return {'status': 'passed', 'checks': [
                'unique aggregate keys', 'finite nonnegative credit bounded by paper count',
                'venue ownership', 'venue-to-area credit reconciliation',
                'area and venue JSON-to-CSV equality', 'complete institution metadata keys',
                *(['author-to-area credit reconciliation within declared rounding bound']
                  if has_authors else []),
                'nonempty default-on areas'],
            'aggregate_rows': len(unique), 'institutions': len(institutions),
            'year_min': min(years), 'year_max': max(years),
            'adjusted_count_by_area': {a: round(totals[a], 5) for a in areas},
            'venues_without_credit': sorted(set(known_venues) - venue_rows.keys()),
            'institutions_without_country': sum(not v.get('country') for v in institutions.values())}


def cached_institutions(cache_dir, registry, wanted):
    """First country and type each wanted institution carries on the field's cached works."""
    found = {}
    venues = [venue['key'] for area in registry['areas'].values() for venue in area['venues']]
    for path in (path for venue in venues for path in sorted((cache_dir / venue).glob('*/works.jsonl'))):
        with path.open() as handle:
            for line in handle:
                for authorship in json.loads(line).get('authorships', []):
                    for inst in authorship.get('institutions', []):
                        iid = inst.get('id')
                        if iid in wanted and iid not in found:
                            found[iid] = {'country': inst.get('country_code') or '', 'type': inst.get('type') or ''}
    return found


def institution_metadata(rows, cache_dir, registry):
    """Name, country and type for every credited institution.

    Type follows the credit path: maintainer overrides, evidenced type
    corrections, the aggregator's own table, then the type on cached works, so
    the site labels an institution by the type it was credited under. Names and
    countries prefer the refreshed records and the OpenAlex snapshot.
    """
    sys.path.insert(0, str(ROOT / 'pipeline'))
    from aggregate import type_corrections
    corrections = type_corrections()
    live_path = ROOT / LIVE_RECORDS
    live = json.loads(live_path.read_text())['by_id'] if live_path.exists() else {}
    snapshot = json.loads((ROOT / 'data/institutions.json').read_text())['by_id']
    override_path = ROOT / 'data/institution-metadata-overrides.json'
    overrides = json.loads(override_path.read_text()) if override_path.exists() else {}
    rows = list(rows)
    cached = cached_institutions(cache_dir, registry, {row['institution_id'] for row in rows})
    metadata = {}
    for row in rows:
        iid = row['institution_id']
        canonical = 'https://openalex.org/' + iid.rstrip('/').split('/')[-1]
        source = live.get(canonical) or snapshot.get(canonical) or {}
        override = overrides.get(canonical, {})
        work = cached.get(iid, {})
        metadata[iid] = {'name': override.get('name') or source.get('display_name') or row['institution_name'],
                         'country': (override.get('country') or source.get('country_code')
                                     or row.get('country') or work.get('country') or ''),
                         'type': (override.get('type') or corrections.get(canonical) or row.get('type')
                                  or work.get('type') or source.get('type') or '')}
    return dict(sorted(metadata.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_field_argument(parser, default='ece')
    parser.add_argument('--cache-dir', required=True, type=pathlib.Path)
    parser.add_argument('--out', required=True, type=pathlib.Path)
    parser.add_argument('--workers', type=int, default=None,
                        help='Aggregation workers (default: available CPU allocation)')
    parser.add_argument('--executor', choices=('auto', 'processes', 'threads'), default='auto')
    parser.add_argument('--sequential', action='store_true', help='Run single-threaded')
    parser.add_argument('--aggregation-cache-dir', type=pathlib.Path,
                        default=ROOT / '.tmp/aggregation-cache')
    parser.add_argument('--no-aggregation-cache', action='store_true')
    parser.add_argument('--refresh-manifest', type=pathlib.Path,
                        required=True,
                        help='Evidence of accepted fresh and retained cache files')
    args = parser.parse_args()
    field = get_field(args.field)
    if args.workers is not None and args.workers < 1:
        parser.error('--workers must be positive')
    if not args.sequential:
        try:
            select_executor(args.executor)
        except ValueError as error:
            parser.error(str(error))
    output = args.out.resolve()
    public_data = (ROOT / field.site_data_dir).resolve()
    if output == public_data or public_data in output.parents or output.exists():
        parser.error(f'Use a new candidate output directory, outside {field.site_data_dir}')
    refresh = json.loads(args.refresh_manifest.read_text())
    inventory = {(row['venue'], str(row['year'])): row for row in refresh.get('files', [])}
    cache_files = {(path.parts[-3], path.parts[-2]): path
                   for path in args.cache_dir.glob('*/*/works.jsonl')}
    if not inventory or set(cache_files) != set(inventory):
        parser.error('Candidate cache must match the complete declared refresh inventory')
    source_hashes = digest_files(cache_files.values(), args.workers)
    for key, path in cache_files.items():
        if source_hashes[path] != inventory[key]['sha256']:
            parser.error(f'Candidate cache hash differs from inventory: {key}')
    initial_hashes = {path: digest(ROOT / path) for path in [
        'data/fields.json', field.areas_file, 'data/affiliation-map.csv', 'data/institution-aliases.csv',
        'data/excluded-works.csv', 'data/institution-metadata-overrides.json',
        'data/institution-metadata-corrections.json',
        'data/institutions.json', LIVE_RECORDS]
        if (ROOT / path).exists()}
    code_hashes = {path: digest(ROOT / path) for path in CODE_FILES}
    output.mkdir(parents=True)
    registry = json.loads((ROOT / field.areas_file).read_text())
    command = [sys.executable, str(ROOT / 'pipeline/aggregate.py'), '--field', field.id, '--all-cached',
               '--cache-dir', str(args.cache_dir.resolve()), '--areas-json', str(ROOT / field.areas_file),
               '--out', str(output),
               '--executor', args.executor, '--aggregation-cache-dir', str(args.aggregation_cache_dir.resolve()),
               '--stats', str(output / 'aggregation-stats.log')]
    if args.workers is not None:
        command += ['--workers', str(args.workers)]
    if args.sequential:
        command.append('--sequential')
    if args.no_aggregation_cache:
        command.append('--no-aggregation-cache')
    with (output / 'aggregate.log').open('w') as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    if (output / 'inst-area-year_edu_only.csv').exists():
        # Biology's aggregator writes education-only and all-institution tables
        # (with hospital rollup). The site ranks the education-only tables.
        for table in ('inst-area-year', 'inst-venue-year'):
            (output / f'{table}_edu_only.csv').replace(output / f'{table}.csv')
        for extra in output.glob('*_all_insts.csv'):
            extra.unlink()
        for extra in output.glob('rankings_summary_*.csv'):
            extra.unlink()
    subprocess.run([sys.executable, str(ROOT / 'pipeline/split.py'), '--field', field.id,
                    '--area-input', str(output / 'inst-area-year.csv'),
                    '--venue-input', str(output / 'inst-venue-year.csv'),
                    '--areas', str(ROOT / field.areas_file), '--out', str(output)],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    metadata = institution_metadata(read_csv(output / 'inst-area-year.csv'), args.cache_dir.resolve(), registry)
    (output / 'institutions.json').write_text(json.dumps(metadata, ensure_ascii=False, separators=(',', ':')) + '\n')
    result = validate(output, registry)
    if any(digest(ROOT / path) != value for path, value in initial_hashes.items()):
        raise ValueError('Curated inputs changed during release build; rebuild from a stable input set')
    if any(digest(ROOT / path) != value for path, value in code_hashes.items()):
        raise ValueError('Build code changed during release build')
    final_cache = {(p.parts[-3], p.parts[-2]): p for p in args.cache_dir.glob('*/*/works.jsonl')}
    if final_cache != cache_files or digest_files(cache_files.values(), args.workers) != source_hashes:
        raise ValueError('Candidate cache changed during release build')
    public_inputs = {'registry': initial_hashes[field.areas_file],
                     'affiliation_map': initial_hashes['data/affiliation-map.csv'],
                     'institution_aliases': initial_hashes['data/institution-aliases.csv'],
                     'excluded_works': initial_hashes['data/excluded-works.csv']}
    for name, path in (('institution_metadata_overrides', 'data/institution-metadata-overrides.json'),
                       ('institution_metadata_corrections', 'data/institution-metadata-corrections.json'),
                       ('institution_metadata_snapshot', 'data/institutions.json'),
                       ('institution_metadata_refresh', LIVE_RECORDS)):
        if path in initial_hashes:
            public_inputs[name] = initial_hashes[path]
    artifacts = {str(path.relative_to(output)): {'sha256': digest(path), 'bytes': path.stat().st_size}
                 for path in sorted(output.rglob('*')) if path.is_file() and path.suffix in ('.csv', '.json')}
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    # LFS clean filters can require writes even for status. A read-only build
    # still has complete code/input hashes; conservatively mark status failures dirty.
    status = subprocess.run(['git', '--no-optional-locks', 'status', '--porcelain'], cwd=ROOT,
                            capture_output=True, text=True)
    dirty = status.returncode != 0 or bool(status.stdout.strip())
    stats_path = output / 'aggregation-stats.log'
    credited = ', '.join(field.default_credit_types)
    manifest = {'schema_version': 1, 'field': field.id, 'description': field.description,
                'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'source_revision': revision, 'source_tree_dirty': dirty,
                'source_tree_status': 'available' if status.returncode == 0 else 'unavailable; assumed dirty',
                'source_revision_meaning': 'Git baseline at build time; code_hashes identify the actual working-tree files, including uncommitted changes.',
                'code_hashes': code_hashes,
                'aggregation': json.loads(stats_path.read_text()) if stats_path.exists() else None,
                'latest_complete_year': datetime.date.today().year - 1,
                'latest_complete_year_meaning': 'Last completed calendar year; publisher coverage may still be incomplete.',
                'earliest_year': field.earliest_year,
                'default_start_year': field.default_start_year,
                'default_end_year': field.default_end_year,
                'methodology': f'Equal 1/N author credit, split between the unique credited institutions ({credited}) each author lists; geometric mean of 1+area counts minus 1.',
                'input_hashes': public_inputs, 'artifacts': artifacts, 'validation': result,
                'refresh': refresh,
                'coverage_note': 'Source indexing and affiliation coverage vary by venue and year. Carried-forward scopes were not refreshed in this build.'}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
