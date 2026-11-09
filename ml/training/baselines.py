"""Run development baselines with visible progress; calibration/test remain locked."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.eligibility import digest
from ml.evaluation.metrics import lower_do_threshold, score_predictions
from ml.modeling.baselines import predict_references
from .data import PreparedRelease
from .experiment import capture_provenance, validate_config


def evaluate_case(observations, index, threshold, policy):
    """Score one development partition/configuration/horizon, with canonical float64 truth."""
    if index.empty or not index.partition.isin(['train', 'validation']).all() or index.partition.nunique() != 1:
        raise ValueError('Only one nonempty development partition may be scored')
    for column in ['configuration', 'horizon_hours', 'session_id']:
        if index[column].nunique() != 1:
            raise ValueError('Score each session/configuration/horizon separately')
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError('Invalid training-frozen lower-DO threshold')
    expected = index.copy()
    truth = observations.set_index('observation_id').do_mgL
    expected['observed_do_mgL'] = expected.target_observation_id.map(truth)
    predictions = {model: predict_references(observations, index, model) for model in policy['baseline_candidates']}
    all_rows, metrics = [], []
    context = {column: index[column].iloc[0] for column in ['partition', 'configuration', 'horizon_hours', 'session_id']}
    context['horizon_hours'] = int(context['horizon_hours'])
    for model, prediction in predictions.items():
        details = prediction.merge(expected[['window_id', 'observed_do_mgL'] + policy['comparison_cohorts']],
                                   on='window_id', validate='one_to_one')
        details['error_mgL'] = (pd.to_numeric(details.point_mgL, errors='coerce') - details.observed_do_mgL).where(details.status.eq('ok'))
        details['absolute_error_mgL'] = details.error_mgL.abs()
        all_rows.append(details)
    for cohort in policy['comparison_cohorts']:
        selected = expected[expected[cohort].eq(True)]
        subsets = {'all_targets': selected, 'training_lower_decile': selected[selected.observed_do_mgL.le(threshold)]}
        for subset, rows in subsets.items():
            reference = predictions['persistence'][predictions['persistence'].window_id.isin(rows.window_id)]
            for model, prediction in predictions.items():
                scored = prediction[prediction.window_id.isin(rows.window_id)]
                result = score_predictions(rows, scored, reference)
                metrics.append({**context, 'model': model, 'cohort': cohort, 'subset': subset, 'seed': None,
                                'primary_rankable': cohort == 'all_horizon_specific' and subset == 'all_targets'
                                    and result['complete_predictions'], **result})
    return pd.concat(all_rows, ignore_index=True), metrics


def run_baselines(config_path, output, repository=None, matrix=False, dry_run=False):
    repository = Path(repository or Path.cwd()).resolve()
    config_path, output = Path(config_path), Path(output)
    if output.exists():
        raise FileExistsError('Use a new output directory: ' + str(output))
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    validate_config(config)
    descriptor = (repository / config['release_descriptor']).resolve()
    if not descriptor.is_relative_to(repository):
        raise ValueError('Release descriptor must be inside the repository')
    print('Verifying the anchored release. Development scoring only; final test/calibration locked.', flush=True)
    release = PreparedRelease(descriptor, repository)
    policy_path = release.root / 'policies/evaluation-policy.json'
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    settings = ([(configuration, horizon) for configuration in release.contract['input_configurations']
                 for horizon in release.contract['horizons_hours']] if matrix
                else [(config['configuration'], config['horizon_hours'])])
    contexts, counts = [], []
    for configuration, horizon in settings:
        for partition in ['train', 'validation']:
            observations, index = release.baseline_context(partition, configuration, horizon)
            contexts.append((observations, index))
            counts.append({'partition': partition, 'configuration': configuration, 'horizon_hours': horizon,
                           **{cohort: int(index[cohort].eq(True).sum()) for cohort in policy['comparison_cohorts']}})
            print(f'{configuration} +{horizon}h {partition}: {len(index)} windows; '
                  f'{int(index.seasonal_matched.sum())} seasonal-matched.', flush=True)
    report = capture_provenance(config_path, config, repository, release)
    report.update({'status': 'baseline_plan_verified' if dry_run else 'development_baselines_scored',
                   'matrix': matrix, 'runtime_device': 'cpu', 'training_performed': False,
                   'learned_transform_fitted': False, 'prediction_scores_computed': not dry_run,
                   'locked_partitions': ['calibration', 'test'], 'evaluation_policy_sha256': digest(policy_path),
                   'seed_used_by_baselines': False, 'cohort_counts': counts})
    all_predictions, all_metrics = [], []
    if not dry_run:
        training = release.training_observations()
        if len(training) != 100:
            raise ValueError('Lower-tail diagnostic must use the 100 frozen training bins')
        threshold = lower_do_threshold(training)
        report['lower_do_diagnostic'] = {'threshold_mgL': threshold, 'fit_partition': 'train', 'distinct_observations': 100,
                                         'quantile': .1, 'method': 'linear', 'biological_safety_threshold': False}
        for number, (observations, index) in enumerate(contexts, 1):
            print(f'[{number}/{len(contexts)}] Computing persistence, seasonal forecasts and matched metrics...', flush=True)
            predictions, metrics = evaluate_case(observations, index, threshold, policy)
            all_predictions.append(predictions)
            all_metrics.extend(metrics)
    else:
        print('Dry run: no baseline predictions, scores or diagnostic threshold computed.', flush=True)
    if config_path.read_bytes() != config_bytes or digest(release.root / 'release_manifest.json') != release.manifest_sha256:
        raise ValueError('Configuration or release manifest changed during the run')
    output.mkdir(parents=True)
    (output / 'config.json').write_bytes(config_bytes)
    (output / 'prepared-release.json').write_bytes(descriptor.read_bytes())
    if not dry_run:
        pd.concat(all_predictions, ignore_index=True).to_csv(output / 'predictions.csv', index=False)
        pd.DataFrame(all_metrics).to_csv(output / 'metrics.csv', index=False)
        (output / 'metrics.json').write_text(json.dumps(all_metrics, indent=2, allow_nan=False), encoding='utf-8')
    report['outputs_sha256'] = {p.name: digest(p) for p in sorted(output.iterdir())}
    (output / 'run.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    if not dry_run:
        print('Validation results on each full horizon-specific cohort (mg/L):', flush=True)
        for row in all_metrics:
            if row['partition'] == 'validation' and row['cohort'] == 'all_horizon_specific' and row['subset'] == 'all_targets':
                print(f"{row['configuration']} +{row['horizon_hours']}h {row['model']}: "
                      f"MAE={row['mae_mgL']}, RMSE={row['rmse_mgL']}, "
                      f"valid={row['valid_predictions']}/{row['expected_windows']}", flush=True)
    print('Saved', output, '. These are development results; no learned model or final-test evaluation.', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('ml/training/configs/do_pilot.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--matrix', action='store_true', help='Run both configurations and both horizons')
    parser.add_argument('--dry-run', action='store_true', help='Verify data/counts without predictions or scoring')
    args = parser.parse_args()
    try:
        run_baselines(args.config, args.output, matrix=args.matrix, dry_run=args.dry_run)
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
