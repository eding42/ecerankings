#!/usr/bin/env python3
"""Promote a verified local candidate into its field's site data directory.

Works the same way for every field (--field ece|biology|earth-space). Raw cache
files are stored through Git LFS where the field's cache is LFS-tracked.

Does not stage Git changes, commit, push, or deploy. Writes the release manifest
last, so the site packager rejects an interrupted or mixed publication.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from fields import add_field_argument, get_field  # noqa: E402

INPUTS = {
    'registry': 'data/areas.json',
    'affiliation_map': 'data/affiliation-map.csv',
    'institution_aliases': 'data/institution-aliases.csv',
    'excluded_works': 'data/excluded-works.csv',
    'institution_metadata_overrides': 'data/institution-metadata-overrides.json',
    'institution_metadata_corrections': 'data/institution-metadata-corrections.json',
    'institution_metadata_snapshot': 'data/institutions.json',
    'institution_metadata_refresh': 'data/refresh/institution-records-2026-10-28.json',
}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def check_inputs(manifest, registry='data/areas.json'):
    inputs = {**INPUTS, 'registry': registry}
    for name, expected in manifest['input_hashes'].items():
        if name not in inputs or digest(ROOT / inputs[name]) != expected:
            raise ValueError(f'Curated input changed since build: {name}')
    for name, expected in manifest.get('code_hashes', {}).items():
        source = (ROOT / name).resolve()
        if not source.is_relative_to(ROOT) or digest(source) != expected:
            raise ValueError(f'Build code changed since build: {name}')


def validate_candidate(cache, release, field=None):
    field = field or get_field('ece')
    manifest = json.loads((release / 'manifest.json').read_text())
    if manifest.get('validation', {}).get('status') != 'passed':
        raise ValueError('A passing candidate release is required')
    if manifest.get('field', 'ece') != field.id:
        raise ValueError(f"Candidate was built for {manifest.get('field', 'ece')}, not {field.id}")
    check_inputs(manifest, field.areas_file)
    for relative, evidence in manifest['artifacts'].items():
        source = (release / relative).resolve()
        if not source.is_relative_to(release) or digest(source) != evidence['sha256']:
            raise ValueError(f'Candidate artifact differs: {relative}')
    inventory = {(r['venue'], str(r['year'])): r for r in manifest['refresh']['files']}
    files = {(p.parts[-3], p.parts[-2]): p for p in cache.glob('*/*/works.jsonl')}
    if not inventory or set(files) != set(inventory):
        raise ValueError('Candidate cache differs from the complete release inventory')
    for key, path in files.items():
        if digest(path) != inventory[key]['sha256']:
            raise ValueError(f'Candidate cache changed: {key}')
    return manifest, files


def atomic_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.release-tmp')
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def export_lfs(source, destination, expected):
    size = source.stat().st_size
    pointer = (f'version https://git-lfs.github.com/spec/v1\noid sha256:{expected}\nsize {size}\n'.encode()
               if size else b'')
    if destination.exists() and destination.read_bytes() == pointer:
        # Keep the normal working tree usable by the data pipeline. Git LFS
        # stores pointers in Git; source files on disk remain materialized.
        atomic_copy(source, destination)
        return False
    with source.open('rb') as handle:
        result = subprocess.run(['git-lfs', 'clean', str(destination.relative_to(ROOT))],
                                stdin=handle, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=ROOT, check=True)
    if result.stdout != pointer:
        raise ValueError(f'LFS clean result differs from candidate: {destination}')
    atomic_copy(source, destination)
    return True


def lfs_tracked(path):
    result = subprocess.run(['git', 'check-attr', 'filter', '--', str(path.relative_to(ROOT))],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    return result.stdout.strip().endswith(': lfs')


def store(source, destination, expected):
    """Copy one file into place, through Git LFS when the destination is LFS-tracked."""
    if lfs_tracked(destination):
        return export_lfs(source, destination, expected)
    if source.resolve() != destination.resolve():
        atomic_copy(source, destination)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_field_argument(parser, default='ece')
    parser.add_argument('--cache-dir', required=True, type=pathlib.Path)
    parser.add_argument('--release', required=True, type=pathlib.Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    field = get_field(args.field)
    cache, release = args.cache_dir.resolve(), args.release.resolve()
    public = (ROOT / field.site_data_dir).resolve()
    if release == public or public in release.parents:
        parser.error(f'Use the separate candidate release, outside {field.site_data_dir}')
    try:
        manifest, files = validate_candidate(cache, release, field)
        if args.check_only:
            print(f'Candidate verified: {len(files)} cache files; no files promoted')
            return
        if not shutil.which('git-lfs'):
            raise ValueError('Install Git LFS before promoting raw cache data')
        required = subprocess.run(['git', 'config', '--get', 'filter.lfs.required'],
                                  cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        if required != 'true':
            raise ValueError('Git LFS must be configured as a required Git filter before promotion')
        inventory = {(r['venue'], str(r['year'])): r for r in manifest['refresh']['files']}
        changed = 0
        for index, ((venue, year), source) in enumerate(sorted(files.items()), 1):
            row = inventory[(venue, year)]
            changed += store(source, ROOT / field.cache_dir / venue / year / 'works.jsonl', row['sha256'])
            if index % 100 == 0:
                print(f'Cache files verified: {index}; changed pointers: {changed}', flush=True)
        for relative, evidence in manifest['artifacts'].items():
            store(release / relative, public / relative, evidence['sha256'])
        # Remove data from venues or areas the release no longer has. Hidden
        # files (the verifier's accepted snapshots) are not release artifacts.
        stale = [path for path in public.rglob('*.json')
                 if path.name != 'manifest.json' and not path.name.startswith('.')
                 and str(path.relative_to(public)) not in manifest['artifacts']]
        for path in stale:
            path.unlink()
        check_inputs(manifest, field.areas_file)
        atomic_copy(release / 'manifest.json', public / 'manifest.json')
        print(f'Promoted {len(files)} materialized cache files ({changed} changed LFS objects) and '
              f'validated public data into {field.site_data_dir}; removed {len(stale)} stale JSON files; '
              'no commit or deployment')
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'Promotion refused: {error}\n')


if __name__ == '__main__':
    main()
