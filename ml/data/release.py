"""Build, verify and compare write-once preparation releases from pinned Oman files."""
import argparse
import contextlib
import gzip
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import pandas as pd

from . import aggregation, eligibility, evaluation_plan, partitions, quality, release_readiness, sessions, windows
from .eligibility import digest


POLICIES = ['sources.json', 'lineage-policy.json', 'release-selection.json', 'partition-policy.json',
            'supervised-contract.json', 'evaluation-policy.json', 'release-criteria.json']


def safe_path(root, relative):
    relative = str(relative).replace('\\', '/')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or ':' in relative:
        raise ValueError('Release path must stay relative to its root')
    target = root / path
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Release path escapes root')
    return target


def content_digest(path):
    import hashlib
    data = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def file_inventory(root):
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinks are not release artifacts')
        if path.is_file() and path != root / 'release_manifest.json':
            files[path.relative_to(root).as_posix()] = {'sha256': digest(path), 'bytes': path.stat().st_size}
    return files


def verify_release(root):
    manifest = json.loads((root / 'release_manifest.json').read_text(encoding='utf-8'))
    if manifest['format_version'] != 1:
        raise ValueError('Unknown release manifest format')
    for relative in manifest['files']:
        safe_path(root, relative)
    actual = file_inventory(root)
    if actual != manifest['files']:
        raise ValueError('Release contains changed, missing or unexpected artifacts')
    for relative, expected in manifest.get('scientific_content_sha256', {}).items():
        if content_digest(safe_path(root, relative)) != expected:
            raise ValueError('Scientific observation content changed')
    return manifest


def environment(requirements):
    expected = {}
    for line in requirements.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            name, version = line.split('==')
            expected[name] = version
    installed = {name: importlib.metadata.version(name) for name in expected}
    if installed != expected or sys.version_info[:2] != (3, 10):
        raise ValueError('Use Python 3.10 and the pinned preparation dependencies')
    for package in ['tensorflow', 'keras', 'torch', 'scikit-learn', 'joblib']:
        try:
            importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
        raise ValueError('Use an isolated preparation-only environment, without ' + package)
    return {'python': platform.python_version(), 'implementation': platform.python_implementation(),
            'platform': platform.platform(), 'dependencies': installed, 'preparation_only_environment': True}


def build(root, policy_dir, output):
    if output.exists():
        raise FileExistsError(output)
    code_dir = Path(__file__).resolve().parent
    requirements = code_dir / 'requirements.txt'
    env = environment(requirements)
    catalog = json.loads((policy_dir / 'sources.json').read_text(encoding='utf-8'))
    source = next(s for s in catalog['sources'] if s['id'] == 'oman_tilapia')
    input_hashes = {}
    source_hashes = {}
    for item in source['downloads']:
        path = safe_path(root, item['relative_path'])
        if digest(path) != item['sha256'] or path.stat().st_size != item['bytes']:
            raise ValueError('Pinned source mismatch: ' + str(path))
        input_hashes[str(path)] = item['sha256']
        source_hashes[item['relative_path']] = item['sha256']
    code_files = sorted(code_dir.glob('*.py')) + [requirements]
    for path in [policy_dir / name for name in POLICIES] + code_files:
        input_hashes[str(path)] = digest(path)
    output.mkdir(parents=True)
    for relative in source_hashes:
        target = safe_path(output / 'sources', relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(safe_path(root, relative).read_bytes())
    for path in code_files:
        target = output / 'code/ml/data' / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    policies = output / 'policies'
    policies.mkdir()
    for name in POLICIES:
        (policies / name).write_bytes((policy_dir / name).read_bytes())
    (output / 'environment.json').write_text(json.dumps(env, indent=2), encoding='utf-8')
    stages = output / 'stages'
    stages.mkdir()
    src = output / 'sources/oman_tilapia'
    with (output / 'build.log').open('w', encoding='utf-8') as log:
        jobs = [
            ('sessions', lambda: sessions.run(src, stages / 'sessions')),
            ('quality', lambda: quality.run(src, stages / 'sessions', stages / 'quality')),
            ('aggregation', lambda: aggregation.run(src, stages / 'sessions', stages / 'quality', stages / 'aggregation')),
            ('eligibility', lambda: eligibility.run(stages / 'aggregation', policies / 'release-selection.json', stages / 'eligibility')),
            ('partitions', lambda: partitions.run(stages / 'aggregation', stages / 'sessions', stages / 'eligibility/eligibility.json',
                policies / 'release-selection.json', policies / 'partition-policy.json', policies / 'lineage-policy.json', stages / 'partitions')),
            ('supervised', lambda: windows.run(stages / 'partitions', policies / 'supervised-contract.json', stages / 'supervised')),
            ('evaluation', lambda: evaluation_plan.run(stages / 'supervised', policies / 'evaluation-policy.json', stages / 'evaluation')),
            ('criteria', lambda: release_readiness.run(stages / 'evaluation', policies / 'release-criteria.json', stages / 'criteria'))]
        for name, job in jobs:
            with contextlib.redirect_stdout(log):
                job()
            log.flush()
            print('Completed', name, flush=True)
    supervised = json.loads((stages / 'supervised/supervised_manifest.json').read_text(encoding='utf-8'))
    split = json.loads((stages / 'partitions/split_manifest.json').read_text(encoding='utf-8'))
    criteria = json.loads((stages / 'criteria/criteria_manifest.json').read_text(encoding='utf-8'))
    counts = {'observations': supervised['observation_rows'], 'windows': supervised['window_rows'],
              'paired_issues': supervised['paired_issue_rows'], 'raw_parents': split['raw_parents'],
              'readiness_rows': criteria['issue_configuration_rows'], 'input_ready_rows': criteria['inputs_ready_rows']}
    if counts != {'observations': 188, 'windows': 640, 'paired_issues': 312, 'raw_parents': 101666,
                  'readiness_rows': 376, 'input_ready_rows': 336}:
        raise ValueError('Release counts differ from reviewed pilot')
    for path, expected in input_hashes.items():
        if digest(Path(path)) != expected:
            raise ValueError('Preparation input changed during build: ' + path)
    files = file_inventory(output)
    scientific = {name: content_digest(output / name) for name in files
                  if name.startswith('stages/') and (name.endswith(('.csv', '.csv.gz', '.jsonl'))
                     or name in ['stages/sessions/inventory.json', 'stages/quality/quality.json'])}
    binding = {name: entry['sha256'] for name, entry in files.items() if name.startswith(('code/', 'policies/', 'sources/'))}
    manifest = {'format_version': 1, 'release_id': 'oman-do-pilot-data-v1', 'training_approved': False,
                'status': 'prepared_candidate_pending_rebuild_comparison', 'source_id': source['id'],
                'source_files_sha256': source_hashes, 'source_url': source['url'], 'declared_license': source['license'],
                'environment': env, 'files': files, 'scientific_content_sha256': scientific,
                'reproduction_binding_sha256': binding, 'counts': counts,
                'claim_scope': 'One publisher-declared Nile tilapia tank, chronological DO pilot; no independent-site, shrimp or interval reliability claim.',
                'model_training_performed': False}
    (output / 'release_manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding='utf-8')
    verify_release(output)
    print('Built and verified candidate:', output, '; counts:', counts)


def compare(first, second, report_path, reference):
    if first.resolve() == second.resolve():
        raise ValueError('Independent output directories required')
    if report_path.exists() or report_path.resolve().is_relative_to(first.resolve()) or report_path.resolve().is_relative_to(second.resolve()):
        raise ValueError('Use a fresh verification report outside the frozen candidates')
    a, b = verify_release(first), verify_release(second)
    for key in ['scientific_content_sha256', 'reproduction_binding_sha256', 'counts', 'environment']:
        if a[key] != b[key]:
            raise ValueError('Reproduction mismatch: ' + key)
    compared = {}
    if reference is not None:
        for name in ['observations.csv.gz', 'windows.jsonl', 'paired_issues.jsonl', 'window_counts.csv', 'paired_issue_counts.csv']:
            current = first / 'stages/supervised' / name
            if content_digest(current) != content_digest(reference / name):
                raise ValueError('Previously reviewed supervised content changed: ' + name)
            compared[name] = content_digest(current)
    report = {'release_id': a['release_id'], 'status': 'ready_for_scoped_model_development',
              'training_approved': True, 'model_training_performed': False, 'production_approved': False,
              'candidate_manifest_sha256': digest(first / 'release_manifest.json'),
              'independent_rebuild_manifest_sha256': digest(second / 'release_manifest.json'),
              'scientific_artifacts_compared': len(a['scientific_content_sha256']),
              'previous_supervised_content_sha256': compared, 'counts': a['counts'],
              'environment': a['environment'], 'claim_scope': a['claim_scope'],
              'note': 'Data-readiness approval only. Stage manifests preserve their earlier not-approved status. Gzip containers and path-bearing stage manifests can differ; decoded scientific content and copied code/policy/source bytes must match.'}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print('Verified independent reproduction:', report_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build_parser = sub.add_parser('build')
    build_parser.add_argument('--root', type=Path, default=Path('Datasets/external'))
    build_parser.add_argument('--policy-dir', type=Path, default=Path('docs/data'))
    build_parser.add_argument('--output', type=Path, required=True)
    verify_parser = sub.add_parser('verify')
    verify_parser.add_argument('release', type=Path)
    compare_parser = sub.add_parser('compare')
    compare_parser.add_argument('first', type=Path)
    compare_parser.add_argument('second', type=Path)
    compare_parser.add_argument('--report', type=Path, required=True)
    compare_parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    if args.command == 'build':
        build(args.root, args.policy_dir, args.output)
    elif args.command == 'verify':
        verify_release(args.release)
        print('Release checksums verified')
    else:
        compare(args.first, args.second, args.report, args.reference)
