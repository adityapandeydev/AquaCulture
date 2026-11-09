"""Inspect a development experiment and record provenance; this command never fits."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ml.data.eligibility import digest
from .data import PreparedRelease
from .runtime import check_device


def validate_config(config):
    fields = {'version', 'release_descriptor', 'configuration', 'horizon_hours', 'seed', 'neural_device'}
    if (set(config) != fields or config['version'] != 'do-experiment-foundation-v1'
            or config['configuration'] not in {'do_only', 'do_temperature_ph'}
            or type(config['horizon_hours']) is not int or config['horizon_hours'] not in {1, 3}
            or type(config['seed']) is not int or config['seed'] not in {17, 29, 43}
            or config['neural_device'] != 'cuda' or not isinstance(config['release_descriptor'], str)
            or not config['release_descriptor']):
        raise ValueError('Configuration differs from the registered development scope')


def capture_provenance(config_path, config, repository, release):
    """Shared metadata for inspections, baselines and later learned-model runs."""
    try:
        git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repository, capture_output=True, text=True, check=False)
        revision = git.stdout.strip() if git.returncode == 0 else None
    except FileNotFoundError:
        revision = None
    files = ([p for folder in ['ml/training', 'ml/data', 'ml/modeling', 'ml/evaluation']
              for p in sorted((repository / folder).rglob('*.py'))]
             + [repository / 'ml/data/requirements.txt', repository / 'ml/training/requirements-gpu-windows.txt'])
    return {'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'config': config, 'config_sha256': digest(config_path), 'release_manifest_sha256': release.manifest_sha256,
              'descriptor_sha256': digest(release.descriptor_path), 'git_revision': revision,
              'source_sha256': {p.relative_to(repository).as_posix(): digest(p) for p in files},
              'python': platform.python_version(),
              'preparation_dependencies': {name: importlib.metadata.version(name) for name in ['numpy', 'pandas', 'openpyxl']}}


def inspect_experiment(config_path, output, repository=None):
    repository = Path(repository or Path.cwd()).resolve()
    config_path, output = Path(config_path), Path(output)
    if output.exists():
        raise FileExistsError('Use a new experiment output directory: ' + str(output))
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    validate_config(config)
    descriptor = (repository / config['release_descriptor']).resolve()
    if not descriptor.is_relative_to(repository):
        raise ValueError('Release descriptor must be inside the repository')
    print('Verifying prepared-release checksums...', flush=True)
    release = PreparedRelease(descriptor, repository)
    batches = {}
    for partition in ['train', 'validation']:
        print('Resolving', partition, 'windows...', flush=True)
        batches[partition] = release.development(partition, config['configuration'], config['horizon_hours'])
    report = capture_provenance(config_path, config, repository, release)
    report.update({'status': 'foundation_verified_no_training',
              'development_partitions': {name: batch.summary() for name, batch in batches.items()},
              'development_window_ids': {name: list(batch.window_ids) for name, batch in batches.items()},
              'locked_partitions': ['calibration', 'test'], 'training_performed': False,
              'learned_transform_fitted': False, 'neural_device_requested': config['neural_device'],
              'gpu_execution_verified': False, 'gpu_note': 'Run doctor in the GPU environment; data inspection does not import PyTorch.'})
    if config_path.read_bytes() != config_bytes:
        raise ValueError('Configuration changed during inspection')
    output.mkdir(parents=True)
    (output / 'config.json').write_bytes(config_bytes)
    (output / 'prepared-release.json').write_bytes(descriptor.read_bytes())
    (output / 'run.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    for partition, batch in batches.items():
        print(partition + ':', batch.summary(), flush=True)
    print('Calibration/test access locked. No training or scoring performed. Saved', output, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect')
    inspect.add_argument('--config', type=Path, default=Path('ml/training/configs/do_pilot.json'))
    inspect.add_argument('--output', type=Path, required=True)
    doctor = sub.add_parser('doctor')
    doctor.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    args = parser.parse_args()
    try:
        if args.command == 'inspect':
            inspect_experiment(args.config, args.output)
        else:
            print(json.dumps(check_device(args.device), indent=2))
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
