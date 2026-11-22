"""One-time descriptive final comparison for the locked Oman DO pilot.

Every locked hash and the saved validation forecasts are checked before any final-test
target is scored. An attempt record is written immediately before that exposure.
"""
import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.eligibility import digest
from ml.data.windows import input_matrix
from ml.training.data import PreparedRelease

from .criteria import validation_error_gates
from .metrics import lower_do_threshold, score_predictions
from .replicas import summarize_replicas
from .reporting import prediction_frame

SEEDS = (17, 29, 43)
CONFIGURATION = 'do_only'


def verify_lock(lock, repository):
    """Check that every locked file still has its recorded bytes."""
    checks = [(lock['release']['descriptor'], lock['release']['descriptor_sha256'])]
    checks += [('docs/data/' + name, value) for name, value in lock['policy_sha256'].items()]
    checks += [(item['run'], item['sha256']) for item in lock['development_evidence'].values()]
    checks += list(lock['inference_and_scoring_source_sha256'].items())
    checks += [(r['path'], r['sha256']) for case in lock['cases'] for r in case['replicas']]
    mismatched = [path for path, expected in checks
                  if not (repository / path).is_file() or digest(repository / path) != expected]
    if mismatched:
        raise ValueError('Locked files are missing or changed: ' + ', '.join(mismatched))
    if any([r['seed'] for r in case['replicas']] != list(SEEDS) for case in lock['cases']):
        raise ValueError('Every registered seed must be locked once per horizon')
    return len(checks)


def cohort(release, partition, horizon):
    """Resolve histories, the frozen index and targets for one partition and horizon."""
    index = release._evaluation
    index = index[index.partition.eq(partition) & index.configuration.eq(CONFIGURATION)
                  & index.horizon_hours.eq(horizon)].sort_values(['session_id', 'issue_time']).reset_index(drop=True)
    windows = {w['window_id']: w for w in release._windows}
    histories = np.stack([input_matrix(release._observations, windows[i], release.contract) for i in index.window_id])
    truth = release._observations.set_index('observation_id').do_mgL
    index['observed_do_mgL'] = index.target_observation_id.map(truth)
    return index, histories


def gru_forecasts(path, histories):
    import torch
    from ml.modeling.gru import load_checkpoint
    torch.set_num_threads(1)
    model, record = load_checkpoint(path, device='cpu')
    if record['features'] != 1:
        raise ValueError('The locked candidate uses dissolved oxygen only')
    with torch.inference_mode():
        return model(torch.as_tensor(histories, dtype=torch.float32)).numpy().astype(np.float64)


def check_parity(lock, repository, release):
    """Reproduce the saved validation forecasts with the locked checkpoints on CPU."""
    saved = pd.read_csv(repository / 'ml/runs/gru-first/predictions.csv')
    saved = saved[saved.model.eq('gru') & saved.partition.eq('validation') & saved.configuration.eq(CONFIGURATION)]
    tolerance, worst = lock['cpu_parity_tolerance'], 0.
    for case in lock['cases']:
        index, histories = cohort(release, 'validation', case['horizon_hours'])
        for replica in case['replicas']:
            rows = saved[saved.horizon_hours.eq(case['horizon_hours']) & saved.seed.eq(replica['seed'])]
            expected = rows.set_index('window_id').point_mgL.loc[index.window_id].to_numpy()
            actual = gru_forecasts(repository / replica['path'], histories)
            if not np.allclose(actual, expected, rtol=tolerance['rtol'], atol=tolerance['atol_mgL']):
                raise ValueError('Saved validation forecasts were not reproduced')
            worst = max(worst, float(np.max(np.abs(actual - expected))))
    return worst


def score_case(index, forecasts, threshold):
    """Score persistence and each seed on the declared cohorts."""
    persistence = forecasts['persistence']
    rows = []
    for name in ['all_horizon_specific', 'common_horizons']:
        selected = index[index[name].eq(True)]
        for subset, part in {'all_targets': selected,
                             'training_lower_decile': selected[selected.observed_do_mgL.le(threshold)]}.items():
            reference = persistence[persistence.window_id.isin(part.window_id)]
            for model, frame in forecasts.items():
                scored = score_predictions(part, frame[frame.window_id.isin(part.window_id)], reference)
                rows.append({'model': model, 'cohort': name, 'subset': subset, **scored})
    return rows


def summarize_case(rows, criteria, horizon):
    primary = {r['model']: r for r in rows if r['cohort'] == 'all_horizon_specific' and r['subset'] == 'all_targets'}
    replicas = [{'seed': s, 'status': 'ok', 'validation': primary[f'gru_seed_{s}']} for s in SEEDS]
    summary = summarize_replicas(replicas)
    limits = criteria['accuracy_limits_by_horizon_hours'][str(horizon)]
    skill = criteria['minimum_mae_skill_vs_persistence']

    def gate(metrics):
        result = validation_error_gates(metrics, primary['persistence'], limits, skill)
        return {'passed': result['passed'], 'reasons': result['reasons']}

    return {'horizon_hours': horizon, 'windows': primary['persistence']['expected_windows'],
            'persistence': primary['persistence'],
            'seeds': {str(s): primary[f'gru_seed_{s}'] for s in SEEDS},
            'gru_mean': summary['mean'], 'gru_range': summary['range'],
            'gates': {'primary_seed_17': gate(primary['gru_seed_17']), 'mean_seeds': gate(summary['mean'])}}


def prepare(lock_path, repository):
    """Run every check that does not need final-test targets."""
    lock = json.loads(Path(lock_path).read_text(encoding='utf-8'))
    files = verify_lock(lock, repository)
    release = PreparedRelease(repository / lock['release']['descriptor'], repository)
    if release.manifest_sha256 != lock['release']['manifest_sha256']:
        raise ValueError('Release manifest differs from the lock')
    threshold = lower_do_threshold(release.training_observations())
    if not np.isclose(threshold, lock['lower_do_diagnostic']['threshold_mgL'], rtol=1e-12, atol=0):
        raise ValueError('Lower-DO threshold differs from the lock')
    parity = check_parity(lock, repository, release)
    print(f'{files} locked files verified. Validation parity within {parity:.2e} mg/L.', flush=True)
    return lock, release, {'locked_files_verified': files, 'validation_parity_max_mgL': parity,
                           'lower_do_threshold_mgL': threshold}


def run(output, lock_path, repository):
    repository, output = Path(repository).resolve(), Path(output)
    if output.exists():
        raise FileExistsError('Use a new output directory: ' + str(output))
    lock, release, checks = prepare(lock_path, repository)
    output.mkdir(parents=True)
    record = {'version': 'oman-do-pilot-final-v1', 'lock_sha256': digest(Path(lock_path)),
              'evaluator_sha256': digest(Path(__file__)), 'python': platform.python_version(),
              'started_at_utc': datetime.now(timezone.utc).isoformat(), **checks, 'status': 'final_test_exposed'}
    (output / 'attempt.json').write_text(json.dumps(record, indent=2), encoding='utf-8')

    criteria = json.loads((repository / 'docs/data/release-criteria.json').read_text(encoding='utf-8'))
    details, metrics, cases = [], [], []
    for case in lock['cases']:
        horizon = case['horizon_hours']
        index, histories = cohort(release, lock['evaluation_partition'], horizon)
        if len(index) != case['expected_final_test_windows']:
            raise ValueError('Final-test cohort size differs from the lock')
        forecasts = {'persistence': prediction_frame(index, histories[:, -1, 0], 'persistence')}
        for replica in case['replicas']:
            name = f"gru_seed_{replica['seed']}"
            forecasts[name] = prediction_frame(index, gru_forecasts(repository / replica['path'], histories), name)
        rows = score_case(index, forecasts, checks['lower_do_threshold_mgL'])
        metrics += [{'horizon_hours': horizon, **r} for r in rows]
        cases.append(summarize_case(rows, criteria, horizon))
        truth = index.observed_do_mgL.to_numpy()
        base = np.abs(forecasts['persistence'].point_mgL.to_numpy() - truth)
        for frame in forecasts.values():
            frame = frame.assign(observed_do_mgL=truth, common_horizons=index.common_horizons.to_numpy())
            frame['error_mgL'] = frame.point_mgL - frame.observed_do_mgL
            frame['absolute_error_minus_persistence_mgL'] = frame.error_mgL.abs() - base
            details.append(frame)
    pd.concat(details).to_csv(output / 'forecasts.csv', index=False)
    pd.DataFrame(metrics).to_csv(output / 'metrics.csv', index=False)
    record.update({'status': 'complete', 'cases': cases})
    (output / 'run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--lock', type=Path, default=Path('docs/models/pilot-evaluation-lock.json'))
    parser.add_argument('--check-only', action='store_true', help='verify the lock and parity, score nothing')
    args = parser.parse_args()
    if args.check_only:
        prepare(args.lock, Path.cwd())
    elif args.output is None:
        parser.error('--output is required')
    else:
        print(json.dumps(run(args.output, args.lock, Path.cwd())['cases'], indent=2))


if __name__ == '__main__':
    main()
