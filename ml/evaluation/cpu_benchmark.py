"""Benchmark bound development artifacts in isolated, single-thread CPU processes."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.eligibility import digest
from ml.training.data import PreparedRelease
from ml.training.experiment import capture_provenance, validate_config


def write_json(path, record):
    path.write_text(json.dumps(record, indent=2, allow_nan=False), encoding='utf-8')


def contained(root, relative):
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError('Artifact paths must remain inside their declared directory')
    return path


def verify_run(root, status, repository, descriptor_sha, manifest_sha):
    record = json.loads((root / 'run.json').read_text(encoding='utf-8'))
    if (record['status'] != status or record['descriptor_sha256'] != descriptor_sha
            or record['release_manifest_sha256'] != manifest_sha or record['locked_partitions'] != ['calibration', 'test']):
        raise ValueError('Use completed development runs bound to this exact release')
    for name, expected in record['outputs_sha256'].items():
        if digest(contained(root, name)) != expected:
            raise ValueError('Experiment output hash mismatch: ' + name)
    for name, expected in record['source_sha256'].items():
        if digest(contained(repository, name)) != expected:
            raise ValueError('Training source changed since the bound experiment: ' + name)
    return record


def assess_resources(warm, cold, artifact_bytes, limits):
    measured = {'model_latency': warm['timings']['model_only']['p95_ms'],
                'preprocessing_latency': warm['timings']['hourly_history_preprocessing_plus_model']['p95_ms'],
                'cold_start': max(c['process_start_to_exit_seconds'] for c in cold),
                'artifact_mib': artifact_bytes / 1024**2,
                'peak_rss_mib': max(r['memory']['peak_rss_bytes'] for r in [warm, *cold]) / 1024**2,
                'parameters': warm['parameter_count'], 'batch32_throughput': warm['batch32_windows_per_second']}
    caps = {'model_latency': limits['maximum_model_only_p95_ms'],
            'preprocessing_latency': limits['maximum_preprocessing_plus_model_p95_ms'],
            'cold_start': limits['maximum_fresh_process_load_and_first_prediction_seconds'],
            'artifact_mib': limits['maximum_primary_artifact_with_transforms_mib'],
            'peak_rss_mib': limits['maximum_peak_process_rss_mib'],
            'parameters': limits['maximum_trainable_parameters_per_candidate']}
    checks = {name: bool(np.isfinite(measured[name]) and measured[name] <= cap) for name, cap in caps.items()}
    checks['batch32_throughput'] = bool(np.isfinite(measured['batch32_throughput'])
                                       and measured['batch32_throughput'] >= limits['minimum_batch32_windows_per_second'])
    return {'passed': all(checks.values()), 'checks': checks, 'failed_checks': [name for name, passed in checks.items() if not passed],
            'measured': measured, 'model_qualified': False, 'final_test': 'locked',
            'scope': 'CPU inference from prepared hourly histories; excludes ingestion, aggregation, HTTP and database'}


def forecast_values(frame, batch, family, configuration, horizon):
    selected = frame[frame.model.eq(family) & frame.configuration.eq(configuration)
                     & frame.horizon_hours.eq(horizon) & frame.partition.eq('validation')]
    if family == 'gru':
        selected = selected[selected.seed.eq(17)]
    if (selected.window_id.duplicated().any() or set(selected.window_id) != set(batch.window_ids)
            or not selected.status.eq('ok').all()):
        raise ValueError('Bound forecasts must completely cover the identical validation windows')
    values = selected.set_index('window_id').loc[list(batch.window_ids), 'point_mgL'].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('Bound forecasts are invalid')
    return values.tolist()


def histories_for(batch):
    return [[{'available_at': (pd.Timestamp(issue) - pd.Timedelta(hours=5 - step)).isoformat(),
              **dict(zip(batch.features, values.tolist()))} for step, values in enumerate(history)]
            for issue, history in zip(batch.issue_times, batch.x)]


def prepare_candidates(release, runs, roots):
    frames = {family: pd.read_csv(root / 'predictions.csv') for family, root in roots.items()}
    if any(not frame.partition.isin(['train', 'validation']).all() for frame in frames.values()):
        raise ValueError('Resource benchmark requires development-only prediction files')
    candidates = []
    for configuration in release.contract['input_configurations']:
        for horizon in release.contract['horizons_hours']:
            batch = release.development('validation', configuration, horizon, dtype=np.float64)
            histories = histories_for(batch)
            for family in ['persistence', 'ridge', 'gru']:
                artifact, case_file, accuracy = None, None, None
                if family != 'persistence':
                    cases = [c for c in runs[family]['cases'] if c['configuration'] == configuration and c['horizon_hours'] == horizon]
                    if len(cases) != 1 or cases[0]['selected'] is None or cases[0]['features'] != list(batch.features):
                        raise ValueError('Expected one complete selected case with the frozen feature order')
                    case = cases[0]
                    relative = f'{configuration}/horizon_{horizon}'
                    filename = 'selected_seed_17.pt' if family == 'gru' else 'selected_model.json'
                    for name in [relative + '/' + filename, relative + '/case.json']:
                        if name not in runs[family]['outputs_sha256']:
                            raise ValueError('Selected artifact/case is not bound by run checksums')
                    artifact = contained(roots[family], relative + '/' + filename)
                    case_file = contained(roots[family], relative + '/case.json')
                    accuracy = case['validation_error_gates']
                values = batch.x[:, -1, 0].tolist() if family == 'persistence' else forecast_values(frames[family], batch, family, configuration, horizon)
                candidates.append({'family': family, 'configuration': configuration, 'horizon_hours': horizon,
                    'seed': 17 if family == 'gru' else None, 'features': list(batch.features), 'histories': histories,
                    'window_ids': list(batch.window_ids), 'partition': 'validation', 'expected_predictions': values,
                    'artifact': str(artifact) if artifact else None, 'artifact_sha256': digest(artifact) if artifact else None,
                    'case_sha256': digest(case_file) if case_file else None,
                    'artifact_with_case_bytes': artifact.stat().st_size + case_file.stat().st_size if artifact else 0,
                    'validation_error_gates': accuracy})
    return candidates


def run_worker(payload, phase, repository):
    env = {**os.environ, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
           'NUMEXPR_NUM_THREADS': '1', 'CUDA_VISIBLE_DEVICES': ''}
    before = time.perf_counter()
    process = subprocess.run([sys.executable, '-B', '-m', 'ml.evaluation.cpu_worker', '--payload', str(payload), '--phase', phase],
                             cwd=repository, env=env, capture_output=True, text=True, timeout=120, check=False)
    elapsed = time.perf_counter() - before
    if process.returncode:
        raise RuntimeError('CPU worker failed: ' + process.stderr[-4000:])
    record = json.loads(process.stdout)
    record['process_start_to_exit_seconds'] = elapsed
    return record


def run_benchmark(config_path, ridge_root, gru_root, output, repository=None, dry_run=False):
    repository = Path(repository or Path.cwd()).resolve()
    config_path, output = Path(config_path), Path(output).resolve()
    roots = {'ridge': Path(ridge_root).resolve(), 'gru': Path(gru_root).resolve()}
    if output.exists():
        raise FileExistsError('Use a new CPU benchmark output directory')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    validate_config(config)
    descriptor = contained(repository, config['release_descriptor'])
    print('Verifying release and completed ridge/GRU runs; held-out partitions stay locked.', flush=True)
    release = PreparedRelease(descriptor, repository)
    runs = {family: verify_run(root, f'development_{family}_completed', repository, digest(descriptor), release.manifest_sha256)
            for family, root in roots.items()}
    criteria_file = release.root / 'policies/release-criteria.json'
    criteria = json.loads(criteria_file.read_text(encoding='utf-8'))
    candidates = prepare_candidates(release, runs, roots)
    report = capture_provenance(config_path, config, repository, release)
    report.update({'status': 'cpu_plan_verified' if dry_run else 'running', 'training_performed': False,
        'locked_partitions': ['calibration', 'test'], 'model_qualified': False, 'criteria_sha256': digest(criteria_file),
        'input_runs': {f: {'run_sha256': digest(p / 'run.json'), 'directory': str(p)} for f, p in roots.items()},
        'protocol': {'warmups': 20, 'single_window_repetitions': 100, 'cold_processes_per_candidate': 3,
                     'batch_size': 32, 'batch_repetitions': 100, 'threads': 1, 'model_only_includes_fitted_transforms': True,
                     'batch_repeats_validation_windows_cyclically': True, 'cpu_only': True},
        'results': [], 'planned_candidates': [{k: v for k, v in c.items() if k not in ['histories', 'expected_predictions']} for c in candidates]})
    output.mkdir(parents=True)
    write_json(output / 'run.json', report)
    try:
        for number, candidate in enumerate(candidates, 1):
            name = f'{candidate["configuration"]}_h{candidate["horizon_hours"]}_{candidate["family"]}'
            payload = output / (name + '_input.json')
            write_json(payload, candidate)
            if dry_run:
                continue
            print(f'[{number}/{len(candidates)}] CPU {name}: 3 cold processes, warm latency and batch32', flush=True)
            cold = [run_worker(payload, 'cold', repository) for _ in range(3)]
            warm = run_worker(payload, 'warm', repository)
            gates = assess_resources(warm, cold, candidate['artifact_with_case_bytes'], criteria['cpu_resource_limits'])
            record = {k: v for k, v in candidate.items() if k not in ['histories', 'expected_predictions']}
            record.update({'cold_trials': cold, 'warm': warm, 'resource_gates': gates})
            write_json(output / (name + '_result.json'), record)
            report['results'].append(record)
            write_json(output / 'run.json', report)
            print(f'  model p95={gates["measured"]["model_latency"]:.4f}ms; peak RSS={gates["measured"]["peak_rss_mib"]:.1f}MiB; resource gates={gates["passed"]}', flush=True)
        # Reject mutation during the experiment, including weights that a worker could otherwise load inconsistently.
        for family, root in roots.items():
            if digest(root / 'run.json') != report['input_runs'][family]['run_sha256']:
                raise ValueError('Bound experiment changed during benchmarking')
            verify_run(root, f'development_{family}_completed', repository, digest(descriptor), release.manifest_sha256)
        if not dry_run:
            report['status'] = 'cpu_benchmark_completed'
            pd.DataFrame([{'family': r['family'], 'configuration': r['configuration'], 'horizon_hours': r['horizon_hours'],
                           'seed': r['seed'], **r['resource_gates']['measured'], 'resource_gates_passed': r['resource_gates']['passed'],
                           'model_qualified': False} for r in report['results']]).to_csv(output / 'summary.csv', index=False)
    except Exception as error:
        report.update({'status': 'failed', 'error': str(error)})
        write_json(output / 'run.json', report)
        raise
    report['outputs_sha256'] = {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file() and p.name != 'run.json'}
    write_json(output / 'run.json', report)
    print('Saved', output, '; no model fitting, candidate promotion or held-out evaluation.', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('ml/training/configs/do_pilot.json'))
    parser.add_argument('--ridge-run', type=Path, default=Path('ml/runs/ridge-first'))
    parser.add_argument('--gru-run', type=Path, default=Path('ml/runs/gru-first'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        run_benchmark(args.config, args.ridge_run, args.gru_run, args.output, dry_run=args.dry_run)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
