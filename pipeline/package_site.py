#!/usr/bin/env python3
"""Package the public static site; exclude raw data, CSVs and development files."""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import tempfile
import datetime
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from fields import add_field_argument, get_field  # noqa: E402
MAX_ASSET = 25 * 1024 * 1024
PACKAGE_MARKER = '.ecerankings-package'
# Sister sites linked from the header, published under the ECE site.
SISTER_SITES = ['biology', 'earth-space']
SISTER_SUFFIXES = {'.html', '.css', '.js', '.json', '.svg', '.png'}


def data_files(site):
    """The published data files of one field's site, in the same layout for every field."""
    registry = json.loads((site / 'data/areas.json').read_text())
    public = ['data/areas.json', 'data/institutions.json', 'data/manifest.json']
    public += [f'data/{area}.json' for area in registry['areas']]
    for area, a_data in registry['areas'].items():
        for venue in a_data.get('venues', []):
            vpath = f"data/{area}/{venue.get('key')}.json"
            if (site / vpath).is_file():
                public.append(vpath)
    return registry, public


def check_data(site, registry, public):
    """Require a passing release manifest whose hashes match every published data file."""
    manifest = json.loads((site / 'data/manifest.json').read_text())
    if manifest.get('validation', {}).get('status') != 'passed':
        raise ValueError(f'A validated release manifest is required before packaging: {site}')
    artifacts = manifest.get('artifacts', {})
    for relative in public:
        if relative.startswith('data/') and relative != 'data/manifest.json':
            expected = artifacts.get(relative.removeprefix('data/'), {}).get('sha256')
            actual = hashlib.sha256((site / relative).read_bytes()).hexdigest()
            if not expected or expected != actual:
                raise ValueError(f'Release manifest hash mismatch: {site.name}/{relative}')
    institutions = json.loads((site / 'data/institutions.json').read_text())
    for area in registry['areas']:
        rows = json.loads((site / f'data/{area}.json').read_text())
        if not isinstance(rows, list):
            raise ValueError(f'Area {area} is not an array')
        absent = {row['i'] for row in rows} - institutions.keys()
        if absent:
            raise ValueError(f'Area {area} has {len(absent)} institutions without metadata')
    return manifest


def check_asset(source, relative):
    if not source.is_file():
        raise ValueError(f'Missing required public asset: {relative}')
    if source.stat().st_size > MAX_ASSET:
        raise ValueError(f'Asset exceeds Cloudflare 25 MiB limit: {relative}')
    if source.read_bytes()[:50].startswith(b'version https://git-lfs.github.com/spec/v1'):
        raise ValueError(f'Unmaterialized Git LFS pointer: {relative}')


def site_files(root, label):
    """Every file of a sister site: its pages and assets, plus its release data files."""
    if not (root / 'index.html').is_file() or not (root / 'data/manifest.json').is_file():
        raise ValueError(f'Missing sister site: {label}')
    registry, public = data_files(root)
    for source in sorted(root.rglob('*')):
        if source.is_symlink():
            raise ValueError(f'Symlink in sister site: {label}/{source.relative_to(root)}')
        relative = source.relative_to(root).as_posix()
        if not source.is_file() or relative.startswith('data/'):
            continue
        if source.suffix not in SISTER_SUFFIXES:
            raise ValueError(f'Unexpected file in sister site: {label}/{relative}')
        public.append(relative)
    for relative in public:
        check_asset(root / relative, f'{label}/{relative}')
    check_data(root, registry, public)
    return public


def sister_files(site):
    return [f'{name}/{relative}' for name in SISTER_SITES for relative in site_files(site / name, name)]


CORE_FILES = [
    'core/engine.js', 'core/rank.js', 'core/rank-history.js', 'core/rank-history.css',
    'core/comparison.js', 'core/comparison.css', 'core/year-strip.js', 'core/year-strip.css',
    'core/coverage.js', 'core/faculty.js', 'core/styles.css',
]


def faculty_files(site):
    """Validate the optional faculty enrichment under its own artifact manifest."""
    root = site / 'faculty'
    if not root.exists():
        return []
    if root.is_symlink() or {p.name for p in root.iterdir()} != {'current.json', 'manifest.json'}:
        raise ValueError('Unexpected or incomplete faculty enrichment bundle')
    if any(p.is_symlink() or not p.is_file() for p in root.iterdir()):
        raise ValueError('Faculty bundle must contain regular files')
    manifest = json.loads((root / 'manifest.json').read_text())
    payload = json.loads((root / 'current.json').read_text())
    expected = manifest.get('artifacts', {}).get('current.json', {}).get('sha256')
    if expected != hashlib.sha256((root / 'current.json').read_bytes()).hexdigest():
        raise ValueError('Faculty manifest hash mismatch')
    if manifest.get('validation', {}).get('status') != 'passed':
        raise ValueError('Validated faculty evidence is required')
    if manifest.get('field') != 'ece' or payload.get('field') != 'ece' or payload.get('schema_version') != 1:
        raise ValueError('Invalid faculty field/schema')
    if not manifest.get('policy_id') or payload.get('policy_id') != manifest['policy_id']:
        raise ValueError('Faculty policy mismatch')
    metrics = {'us-ece-current-v3': 'ece_regular_faculty', 'us-ece-affiliated-v4': 'ece_affiliated_faculty', 'us-ece-affiliated-v5': 'ece_affiliated_faculty'}
    policy_id = manifest['policy_id']
    metric = payload.get('metric_id', 'ece_regular_faculty' if policy_id == 'us-ece-current-v3' else None)
    if policy_id not in metrics or metric != metrics[policy_id] or manifest.get('metric_id', metric) != metric:
        raise ValueError('Faculty metric/policy mismatch')
    seen = set()
    for school in payload.get('schools', []):
        iid = school.get('institution_id')
        if iid in seen or not re.fullmatch(r'https://openalex.org/I\d+', iid or ''):
            raise ValueError('Invalid or duplicate faculty institution')
        seen.add(iid)
        if type(school.get('headcount')) is not int or school['headcount'] < 0:
            raise ValueError('Unresolved faculty count in public bundle')
        incoming = school.get('incoming_headcount', 0)
        current = school.get('current_headcount', school['headcount'] - incoming) if type(incoming) is int else None
        if type(incoming) is not int or incoming < 0 or type(current) is not int or current < 0 or current + incoming != school['headcount']:
            raise ValueError('Invalid current/incoming faculty count breakdown')
        if school.get('policy_id') != manifest['policy_id']:
            raise ValueError('Faculty record policy mismatch')
        datetime.date.fromisoformat(school['observed_on'])
        if not school.get('roster_url', '').startswith('https://'):
            raise ValueError('Faculty count requires official source link')
    return ['faculty/current.json', 'faculty/manifest.json']


def package(site, output):
    if output.is_symlink() or (output.exists() and (
            not output.is_dir() or (any(output.iterdir()) and not (output / PACKAGE_MARKER).is_file()))):
        raise ValueError('Refusing to replace an existing directory not generated by this packager')
    public = ['index.html', '404.html', 'methodology.html', 'coverage.html', 'styles.css', 'main.js',
              'rank.js', 'rank-history.js', 'rank-history.css', 'comparison.js', 'comparison.css', 'year-strip.js', 'year-strip.css', 'coverage.js', 'coverage-data.json', 'favicon.svg', 'apple-touch-icon.png', 'og.png', '_headers', 'robots.txt', 'sitemap.xml']
    public += CORE_FILES
    registry, data = data_files(site)
    public += data
    public += faculty_files(site)
    public += sister_files(site)
    # Institution pages come from prerender_site.mjs, together with the ranking in index.html.
    pages = sorted(p.relative_to(site).as_posix() for p in (site / 'institution').rglob('*') if p.is_file())
    if 'institution/index.html' not in pages or any(not p.endswith('/index.html') for p in pages):
        raise ValueError('institution/ is missing or holds unexpected files; run: node pipeline/prerender_site.mjs')
    public += pages
    for relative in public:
        if relative.split('/')[0] not in SISTER_SITES:
            check_asset(site / relative, relative)
    manifest = check_data(site, registry, data)
    prerendered = re.search(r'<tbody id="ranking-body" data-prerender="([0-9a-f]{64})">', (site / 'index.html').read_text())
    if not prerendered or prerendered.group(1) != hashlib.sha256((site / 'data/manifest.json').read_bytes()).hexdigest():
        raise ValueError('index.html ranking is out of date; run: node pipeline/prerender_site.mjs')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ecerankings-package-', dir=output.parent) as tmp:
        stage = pathlib.Path(tmp) / 'public'
        for relative in public:
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(site / relative, destination)
        try:
            revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            revision = None
        try:
            dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.CalledProcessError):
            dirty = None
        release = {'schema_version': 1, 'project': 'ecerankings', 'build_time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source_revision': revision, 'source_tree_dirty': dirty, 'dataset_generated_at': manifest.get('generated_at'), 'dataset_manifest_sha256': hashlib.sha256((site / 'data/manifest.json').read_bytes()).hexdigest(), 'latest_complete_calendar_year': manifest.get('latest_complete_year')}
        (stage / 'version.json').write_text(json.dumps(release, indent=2) + '\n')
        (stage / PACKAGE_MARKER).write_text('Generated by pipeline/package_site.py\n')
        install_package_atomic(stage, output)
    return len(public), sum((output / p).stat().st_size for p in public)


def install_package_atomic(stage, output):
    """Atomically install a staged package into output, preserving rollback state."""
    backup = None
    if output.exists():
        backup = output.parent / f"{output.name}-backup-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        output.rename(backup)
    try:
        stage.rename(output)
    except Exception:
        if backup and backup.exists() and not output.exists():
            backup.rename(output)
        raise
    else:
        if backup and backup.exists():
            shutil.rmtree(backup)


def package_sister_site(field_cfg, site_path, output):
    if output.is_symlink() or (output.exists() and (
            not output.is_dir() or (any(output.iterdir()) and not (output / PACKAGE_MARKER).is_file()))):
        raise ValueError('Refusing to replace an existing directory not generated by this packager')
    public = site_files(site_path, field_cfg.id)
    manifest = json.loads((site_path / 'data/manifest.json').read_text())

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ecerankings-package-', dir=output.parent) as tmp:
        stage = pathlib.Path(tmp) / 'public'
        for rel in public:
            dest = stage / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(site_path / rel, dest)
        for core_file in CORE_FILES:
            src = ROOT / 'site' / core_file
            if src.is_file():
                dest = stage / core_file
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
        try:
            revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            revision = None
        try:
            dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.CalledProcessError):
            dirty = None
        release = {
            'schema_version': 1,
            'project': f'ecerankings-{field_cfg.id}',
            'build_time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source_revision': revision,
            'source_tree_dirty': dirty,
            'dataset_generated_at': manifest.get('generated_at'),
            'dataset_manifest_sha256': hashlib.sha256((site_path / 'data/manifest.json').read_bytes()).hexdigest(),
            'latest_complete_calendar_year': manifest.get('latest_complete_year'),
        }
        (stage / 'version.json').write_text(json.dumps(release, indent=2) + '\n')
        (stage / PACKAGE_MARKER).write_text('Generated by pipeline/package_site.py\n')
        install_package_atomic(stage, output)
    total_files = len(public) + len(CORE_FILES)
    total_size = sum((output / p).stat().st_size for p in public) + sum((output / c).stat().st_size for c in CORE_FILES if (output / c).is_file())
    return total_files, total_size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_field_argument(parser, default="ece")
    parser.add_argument('--site', type=pathlib.Path, default=None,
                        help='Root directory of the static site to package (default: field-specific site path)')
    parser.add_argument('--out', type=pathlib.Path, default=ROOT / 'dist',
                        help='Directory to write packaged site distribution (default: dist)')
    args = parser.parse_args()

    field_cfg = get_field(args.field) if args.field else get_field("ece")
    site_path = args.site.resolve() if args.site else pathlib.Path(field_cfg.site_path).resolve()
    output = args.out.resolve()

    if output == site_path or output in site_path.parents or site_path in output.parents:
        parser.error('Output must be separate from the source site')

    if field_cfg.id in SISTER_SITES:
        print(f"Packaging {field_cfg.name} static site ({site_path}) into {output}...")
        files, size = package_sister_site(field_cfg, site_path, output)
        print(f'Packaged {files} validated public files ({size / 1024 / 1024:.1f} MiB) into {output}')
        return

    files, size = package(site_path, output)
    print(f'Packaged {files} validated public files ({size / 1024 / 1024:.1f} MiB) into {output}')


if __name__ == '__main__':
    main()
