"""Immutable faculty observations and atomic accepted pointers (stdlib only)."""
from collections import Counter
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


@contextmanager
def lock(root):
    name='ecerankings-faculty-'+digest(str(Path(root).resolve()).encode())[:20]+'.lock'
    with (Path(tempfile.gettempdir())/name).open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def read(path):
    return json.loads(Path(path).read_text())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_hash(source):
    """Keep rendered browser captures distinct from unavailable HTTP bytes."""
    return source.get('capture_sha256') if source.get('capture_format')=='browser_dom' else source.get('response_sha256')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f'Refusing symlink: {path}')
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_write(path, encoded(value))


def put(root, folder, value):
    """Content-addressed factual evidence or observation; never overwrite it."""
    body = encoded(value)
    relative = f'{folder}/{digest(body)}.json'
    path = Path(root) / relative
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError('Immutable artifact differs')
    else:
        atomic_write(path, body)
    return {'file': relative, 'sha256': digest(body)}


def load_ref(root, ref):
    root = Path(root).resolve()
    relative = Path(ref['file'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Artifact reference escapes faculty store')
    path = root / relative
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError('Symlink in artifact reference')
    if not path.resolve().is_relative_to(root):
        raise ValueError('Artifact reference escapes faculty store')
    body = path.read_bytes()
    if digest(body) != ref['sha256']:
        raise ValueError(f'Artifact checksum differs: {relative}')
    return json.loads(body)


def accepted(root):
    index = read(Path(root) / 'accepted.json')
    return index, {school: load_ref(root, ref) for school, ref in index['schools'].items()}


def dependencies(root, snapshot):
    """Verify and return the evidence/review lineage, including prior observations."""
    pending=[snapshot];seen={}
    while pending:
        value=pending.pop()
        refs=list(value.get('evidence',{}).values())
        if value.get('parent'):refs.append(value['parent'])
        refs.extend(value.get('review',{})[key] for key in ('candidate','validation','independent_evidence','audit') if value.get('review',{}).get(key))
        refs.extend(value[key] for key in ('job','brief','candidate','capture_packet','reassessment_of','prior_review') if isinstance(value.get(key),dict) and 'sha256' in value[key])
        normalized=value.get('receipt',{}).get('normalized_output')
        if isinstance(normalized,dict) and 'sha256' in normalized:refs.append(normalized)
        for ref in refs:
            if ref['file'] in seen:
                if seen[ref['file']]!=ref['sha256']:raise ValueError('Inconsistent lineage reference')
                continue
            child=load_ref(root,ref);seen[ref['file']]=ref['sha256']
            pending.append(child)
            if value.get('review',{}).get('validation')==ref and child.get('status')!='passed':raise ValueError('Imported baseline validation failed')
    return seen


def observation_policy(root, snapshot, allow_historical=False):
    """Resolve the exact policy bytes; historical reads never authorize acceptance."""
    active = Path(root) / 'policy.json'
    body = active.read_bytes()
    if digest(body) != snapshot['policy_sha256']:
        if not allow_historical or not re.fullmatch(r'[a-z][a-z0-9-]*', snapshot['policy_id']):
            raise ValueError('Observation policy changed; recollect/review explicitly')
        body = load_policy_bytes(root, snapshot['policy_id'])
    policy = json.loads(body)
    if digest(body) != snapshot['policy_sha256'] or policy['id'] != snapshot['policy_id']:
        raise ValueError('Observation policy changed; archived policy checksum differs')
    return policy


def load_policy_bytes(root, policy_id):
    path = Path(root) / 'policies' / (policy_id + '.json')
    if path.is_symlink():
        raise ValueError('Symlink in archived policy')
    return path.read_bytes()


def summarize(snapshot, policy=None):
    statuses = Counter()
    incoming = 0
    for person in snapshot['people']:
        appointments = [a for a in person['appointments'] if a['institution_id'] == snapshot['institution_id']]
        if len(appointments) != 1:
            raise ValueError('Expected one reviewed appointment per person and school')
        appointment = appointments[0]
        statuses[appointment['decision']['status']] += 1
        incoming += appointment['decision']['status'] == 'included' and appointment['current_state'] == 'incoming'
    ready = snapshot['coverage']['complete'] and not statuses['unresolved'] and snapshot['review']['reconciled']
    return dict(school=snapshot['school'], institution_id=snapshot['institution_id'], name=snapshot['name'],
                unit=snapshot['unit'], state='verified' if ready else 'review_required',
                headcount=statuses['included'] if ready else None, incoming_headcount=incoming if ready else None,
                current_headcount=statuses['included']-incoming if ready else None,
                included_candidates=statuses['included'], excluded=statuses['excluded'], unresolved=statuses['unresolved'],
                reviewed_entries=len(snapshot['people']), observed_on=snapshot['observed_on'],
                policy_id=snapshot['policy_id'], roster_url=snapshot['roster_url'],
                source_urls=sorted({s['url'] for s in snapshot['sources']}),
                metric_id=(policy or snapshot).get('metric_id', 'ece_regular_faculty'),
                count_basis=(policy or snapshot).get('count_basis', 'Official university regular and in-residence EE/ECE faculty, including announced incoming appointments; headcount, not FTE.'))


def check_snapshot(root, snapshot, policy, validate_people, require_review=True, allow_historical_policy=False):
    if not re.fullmatch('[a-z][a-z0-9-]*', snapshot['school']):
        raise ValueError('Invalid school identifier')
    pinned_policy = observation_policy(root, snapshot, allow_historical_policy)
    if pinned_policy != policy:
        raise ValueError('Observation policy changed; recollect/review explicitly')
    sources = {s['id']: s for s in snapshot['sources']}
    if len(sources) != len(snapshot['sources']):
        raise ValueError('Duplicate source identity')
    dependencies(root,snapshot)
    errors = validate_people(snapshot['people'], policy, sources)
    if errors:
        raise ValueError('\n'.join(errors))
    if require_review:
        if snapshot['failures'] or not snapshot['coverage']['complete'] or not snapshot['people']:
            raise ValueError('Incomplete or failed collection cannot replace accepted data')
        if not snapshot['review']['reconciled'] or summarize(snapshot)['unresolved']:
            raise ValueError('Observation still requires review')
        if snapshot.get('workflow_version',1)>=2:
            import faculty_audit
            if not snapshot['review'].get('audit'):raise ValueError('Independent agent audit is required before acceptance')
            faculty_audit.check_bundle(root,snapshot['review']['audit'],snapshot['review']['candidate'],snapshot['review'],snapshot,
                                      historical_policy=policy if allow_historical_policy else None)
    return summarize(snapshot, policy)
