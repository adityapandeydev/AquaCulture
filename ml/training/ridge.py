"""Train the registered CPU ridge reference with checkpoints and development-only selection."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.eligibility import digest
from ml.evaluation.criteria import validation_error_gates
from ml.evaluation.metrics import lower_do_threshold, score_predictions
from ml.evaluation.reporting import evaluate_predictions, prediction_frame
from ml.modeling.baselines import predict_references
from ml.modeling.ridge import RidgeForecaster, fit_ridge
from .data import PreparedRelease
from .experiment import capture_provenance, validate_config


def validate_settings(settings, maximum_settings):
    if (settings['version'] != 'ridge-lag-settings-v1' or settings['alphas'] != [.1, 1., 10., 100.]
            or len(settings['alphas']) > maximum_settings or settings['dtype'] != 'float64'
            or settings['standardization'] != 'training_only_population_mean_and_std'
            or settings['intercept'] != 'training_target_mean_unpenalized'
            or settings['objective'] != 'sum_squared_training_errors_plus_alpha_times_squared_standardized_coefficients'
            or settings['selection'] != 'minimum_complete_full_cohort_validation_mae_then_registered_order_for_equal_cost_ridge_ties'):
        raise ValueError('Use the four preregistered positive ridge settings and preprocessing rules')


def choose_trial(trials):
    eligible = [row for row in trials if row['status'] == 'ok' and row['validation']['complete_predictions']
                and row['validation']['mae_mgL'] is not None and np.isfinite(row['validation']['mae_mgL'])]
    return min(eligible, key=lambda row: (row['validation']['mae_mgL'], row['trial_index'])) if eligible else None


def _json(path, record):
    path.write_text(json.dumps(record, indent=2, allow_nan=False), encoding='utf-8')


def _expected(observations, index):
    return index.assign(observed_do_mgL=index.target_observation_id.map(observations.set_index('observation_id').do_mgL))


def train_case(train, validation, contexts, settings, criteria, output, emit):
    output.mkdir(parents=True)
    trials = []
    expected = {name: _expected(obs, index) for name, (obs, index) in contexts.items()}
    persistence = {name: predict_references(obs, index, 'persistence') for name, (obs, index) in contexts.items()}
    for number, alpha in enumerate(settings['alphas'], 1):
        emit(f'  Trial {number}/{len(settings["alphas"])}: alpha={alpha}; fitting training-only scaler and coefficients')
        trial = {'trial_index': number, 'alpha': alpha, 'status': 'failed'}
        started = time.perf_counter()
        try:
            model = fit_ridge(train.x, train.y, alpha)
            forecasts = {'train': prediction_frame(contexts['train'][1], model.predict(train.x), 'ridge'),
                         'validation': prediction_frame(contexts['validation'][1], model.predict(validation.x), 'ridge')}
            elapsed = time.perf_counter() - started
            if elapsed > criteria['search_limits']['maximum_wall_seconds_per_fit']:
                raise TimeoutError('Per-fit wall-time budget exceeded')
            metrics = {name: score_predictions(expected[name], values, persistence[name]) for name, values in forecasts.items()}
            checkpoint = output / f'trial_{number:02d}'
            checkpoint.mkdir()
            model.save(checkpoint / 'model.json')
            pd.concat(forecasts.values(), ignore_index=True).to_csv(checkpoint / 'predictions.csv', index=False)
            trial.update({'status': 'ok', 'fit_and_predict_seconds': elapsed, 'train': metrics['train'],
                          'validation': metrics['validation'], 'model_path': f'trial_{number:02d}/model.json'})
            emit(f'    validation MAE={metrics["validation"]["mae_mgL"]}; '
                 f'coverage={metrics["validation"]["prediction_coverage"]}; checkpoint saved')
        except (ValueError, np.linalg.LinAlgError, TimeoutError) as error:
            trial.update({'error': str(error), 'fit_and_predict_seconds': time.perf_counter() - started})
            emit('    trial failed: ' + str(error))
        trials.append(trial)
        _json(output / 'trials.json', trials)
    chosen = choose_trial(trials)
    if chosen is None:
        return {'status': 'no_complete_validation_candidate', 'trials': trials, 'selected': None}, None
    selected = RidgeForecaster.load(output / chosen['model_path'])
    selected.save(output / 'selected_model.json')
    baseline = score_predictions(expected['validation'], persistence['validation'])
    horizon = int(contexts['validation'][1].horizon_hours.iloc[0])
    gates = validation_error_gates(chosen['validation'], baseline,
                                   criteria['accuracy_limits_by_horizon_hours'][str(horizon)],
                                   criteria['minimum_mae_skill_vs_persistence'])
    record = {'status': 'development_artifact_only', 'selected_trial': chosen['trial_index'], 'selected_alpha': chosen['alpha'],
              'features': list(train.features), 'input_shape': list(train.x.shape[1:]), 'dtype': str(train.x.dtype),
              'train_window_ids': list(train.window_ids), 'validation_window_ids': list(validation.window_ids),
              'parameter_count': int(selected.coefficients.size + 1), 'validation_error_gates': gates,
              'selected': chosen, 'trials': trials, 'final_test': 'locked', 'model_qualified': False}
    _json(output / 'case.json', record)
    emit(f'  Selected alpha={chosen["alpha"]}; validation error gates passed={gates["passed"]}; final test locked')
    return record, selected


def run_ridge(config_path, settings_path, output, repository=None, matrix=False, dry_run=False):
    repository = Path(repository or Path.cwd()).resolve()
    config_path, settings_path, output = Path(config_path), Path(settings_path), Path(output)
    if output.exists():
        raise FileExistsError('Use a new experiment directory: ' + str(output))
    config_bytes, settings_bytes = config_path.read_bytes(), settings_path.read_bytes()
    config, settings = json.loads(config_bytes), json.loads(settings_bytes)
    validate_config(config)
    descriptor = (repository / config['release_descriptor']).resolve()
    if not descriptor.is_relative_to(repository):
        raise ValueError('Release descriptor must stay inside the repository')
    print('Verifying the frozen release. Ridge uses CPU; calibration and final test remain locked.', flush=True)
    release = PreparedRelease(descriptor, repository)
    criteria_path, policy_path = release.root / 'policies/release-criteria.json', release.root / 'policies/evaluation-policy.json'
    criteria, policy = json.loads(criteria_path.read_text(encoding='utf-8')), json.loads(policy_path.read_text(encoding='utf-8'))
    validate_settings(settings, criteria['search_limits']['maximum_settings_per_family_configuration_horizon'])
    cases = ([(configuration, horizon) for configuration in release.contract['input_configurations']
              for horizon in release.contract['horizons_hours']] if matrix else [(config['configuration'], config['horizon_hours'])])
    prepared = []
    for configuration, horizon in cases:
        batches = {name: release.development(name, configuration, horizon, dtype=np.float64) for name in ['train', 'validation']}
        contexts = {name: release.baseline_context(name, configuration, horizon) for name in batches}
        for name, (_, index) in contexts.items():
            if tuple(index.window_id) != batches[name].window_ids:
                raise ValueError('Model arrays and evaluation windows are not aligned')
        print(f'{configuration} +{horizon}h: train={len(batches["train"].y)}, validation={len(batches["validation"].y)}, '
              f'features={batches["train"].features}', flush=True)
        prepared.append((configuration, horizon, batches, contexts))
    report = capture_provenance(config_path, config, repository, release)
    report.update({'status': 'ridge_plan_verified' if dry_run else 'running', 'matrix': matrix, 'runtime_device': 'cpu',
                   'settings': settings, 'settings_sha256': digest(settings_path), 'seed_used': False,
                   'criteria_sha256': digest(criteria_path), 'evaluation_policy_sha256': digest(policy_path),
                   'training_performed': False, 'training_attempted': not dry_run, 'model_qualified': False,
                   'learned_transform_fitted': False, 'prediction_scores_computed': False,
                   'planned_cases': [{'configuration': c, 'horizon_hours': h,
                                      'partitions': {name: batch.summary() for name, batch in batches.items()}}
                                     for c, h, batches, _ in prepared],
                   'locked_partitions': ['calibration', 'test'], 'cases': []})
    output.mkdir(parents=True)
    (output / 'config.json').write_bytes(config_bytes)
    (output / 'settings.json').write_bytes(settings_bytes)
    (output / 'prepared-release.json').write_bytes(descriptor.read_bytes())
    _json(output / 'run.json', report)
    all_predictions, all_metrics = [], []
    with (output / 'progress.log').open('w', encoding='utf-8') as log:
        def emit(message):
            print(message, flush=True)
            log.write(message + '\n')
            log.flush()
        if dry_run:
            emit('Dry run verified. No scaler, coefficients, threshold, predictions or scores fitted/computed.')
        else:
            training = release.training_observations()
            if len(training) != 100:
                raise ValueError('Expected 100 distinct training bins for the lower-tail diagnostic')
            threshold = lower_do_threshold(training)
            report['lower_do_diagnostic'] = {'threshold_mgL': threshold, 'fit_partition': 'train', 'distinct_observations': 100}
            for number, (configuration, horizon, batches, contexts) in enumerate(prepared, 1):
                emit(f'[{number}/{len(prepared)}] {configuration} +{horizon}h')
                case_path = output / configuration / f'horizon_{horizon}'
                record, model = train_case(batches['train'], batches['validation'], contexts, settings, criteria, case_path, emit)
                report['cases'].append({'configuration': configuration, 'horizon_hours': horizon,
                                        'case_directory': case_path.relative_to(output).as_posix(), **record})
                report['training_performed'] = report['training_performed'] or any(t['status'] == 'ok' for t in record['trials'])
                report['learned_transform_fitted'] = report['training_performed']
                report['prediction_scores_computed'] = report['training_performed']
                _json(output / 'run.json', report)
                if model is not None:
                    for name, (observations, index) in contexts.items():
                        predictions = {baseline: predict_references(observations, index, baseline) for baseline in policy['baseline_candidates']}
                        predictions['ridge'] = prediction_frame(index, model.predict(batches[name].x), 'ridge')
                        details, metrics = evaluate_predictions(observations, index, predictions, threshold, policy)
                        all_predictions.append(details)
                        all_metrics.extend(metrics)
            if all_predictions:
                pd.concat(all_predictions, ignore_index=True).to_csv(output / 'predictions.csv', index=False)
                pd.DataFrame(all_metrics).to_csv(output / 'metrics.csv', index=False)
                _json(output / 'metrics.json', all_metrics)
            report['status'] = 'development_ridge_completed' if all(c['selected'] is not None for c in report['cases']) else 'development_ridge_incomplete'
    if config_path.read_bytes() != config_bytes or settings_path.read_bytes() != settings_bytes:
        raise ValueError('Experiment configuration changed during the run')
    report['outputs_sha256'] = {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob('*'))
                                if p.is_file() and p != output / 'run.json'}
    _json(output / 'run.json', report)
    print('Saved', output, '; models remain development-only. No calibration/final-test evaluation.', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('ml/training/configs/do_pilot.json'))
    parser.add_argument('--settings', type=Path, default=Path('ml/training/configs/ridge_settings.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--matrix', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        run_ridge(args.config, args.settings, args.output, matrix=args.matrix, dry_run=args.dry_run)
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
