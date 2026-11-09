"""CUDA-only development experiments for the registered compact GRU family."""
import argparse
import importlib.metadata
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.eligibility import digest
from ml.evaluation.criteria import validation_error_gates
from ml.evaluation.metrics import lower_do_threshold, score_predictions
from ml.evaluation.replicas import choose_setting, summarize_replicas
from ml.evaluation.reporting import evaluate_predictions, prediction_frame
from ml.modeling.baselines import predict_references
from .data import PreparedRelease
from .experiment import capture_provenance, validate_config
from .gru_fit import fit_replica, prepare_randomness
from .runtime import check_device


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def validate_settings(settings, criteria, policy):
    registered = {'version': 'compact-gru-settings-v1',
                  'settings': [{'hidden_size': h, 'learning_rate': rate} for h in [8, 16] for rate in [.001, .003]],
                  'maximum_epochs': 100, 'patience': 15, 'batch_size': 16, 'weight_decay': .01, 'gradient_clip_norm': 1.,
                  'architecture': 'single_layer_gru_linear_residual_from_latest_do',
                  'scaling': 'training_window_channel_population_mean_std',
                  'loss': 'mean_squared_do_change_scaled_by_training_do_std',
                  'selection': 'complete_validation_mean_seed_mae_then_parameter_count_then_registered_order'}
    if settings != registered or len(settings['settings']) > criteria['search_limits']['maximum_settings_per_family_configuration_horizon']:
        raise ValueError('Use the registered four GRU settings without expanding the search')
    if settings['maximum_epochs'] > criteria['search_limits']['maximum_epochs_per_stochastic_fit']:
        raise ValueError('Epoch budget exceeds frozen criteria')
    if policy['random_seeds_for_stochastic_candidates'] != [17, 29, 43]:
        raise ValueError('Unexpected stochastic replica policy')


def train_case(batches, contexts, settings, criteria, policy, output, emit):
    output.mkdir(parents=True)
    expected, persistence = {}, {}
    for name, (observations, index) in contexts.items():
        expected[name] = index.assign(observed_do_mgL=index.target_observation_id.map(observations.set_index('observation_id').do_mgL))
        persistence[name] = predict_references(observations, index, 'persistence')
    trials, forecasts_by_trial = [], {}
    for number, setting in enumerate(settings['settings'], 1):
        emit(f'  Setting {number}/4: hidden={setting["hidden_size"]}, learning_rate={setting["learning_rate"]}')
        replicas, trial_forecasts = [], {}
        for seed in policy['random_seeds_for_stochastic_candidates']:
            path = output / f'trial_{number:02d}' / f'seed_{seed}'
            try:
                info, values = fit_replica(batches['train'], batches['validation'], setting, settings, seed, 'cuda:0', path,
                                          criteria['search_limits']['maximum_wall_seconds_per_fit'],
                                          criteria['cpu_resource_limits']['maximum_trainable_parameters_per_candidate'], emit)
                predictions = {name: prediction_frame(contexts[name][1], value, 'gru') for name, value in values.items()}
                scores = {name: score_predictions(expected[name], value, persistence[name]) for name, value in predictions.items()}
                replica = {**info, 'status': 'ok', **scores, 'checkpoint': path.relative_to(output).as_posix() + '/best.pt'}
                pd.concat(predictions.values(), ignore_index=True).to_csv(path / 'predictions.csv', index=False)
                trial_forecasts[seed] = predictions
            except (ValueError, TimeoutError) as error:
                # Device/runtime failures abort the experiment rather than becoming a hidden fallback.
                replica = {'seed': seed, 'status': 'failed', 'error': str(error)}
                emit(f'    seed={seed} failed: {error}')
            replicas.append(replica)
            write_json(output / 'progress.json', {'trial_index': number, 'replicas': replicas})
        summary = summarize_replicas(replicas)
        trial = {'trial_index': number, 'setting': setting, 'replicas': replicas, 'summary': summary,
                 'parameter_count': next((r['parameter_count'] for r in replicas if r['status'] == 'ok'), 10001)}
        trials.append(trial)
        forecasts_by_trial[number] = trial_forecasts
        write_json(output / 'trials.json', trials)
    chosen = choose_setting(trials)
    if chosen is None:
        return {'status': 'no_complete_validation_candidate', 'selected': None, 'trials': trials}, None
    horizon = str(int(contexts['validation'][1].horizon_hours.iloc[0]))
    baseline = score_predictions(expected['validation'], persistence['validation'])
    primary = next(r for r in chosen['replicas'] if r['seed'] == 17)
    gates = {name: validation_error_gates(metrics, baseline, criteria['accuracy_limits_by_horizon_hours'][horizon],
                                        criteria['minimum_mae_skill_vs_persistence'])
             for name, metrics in [('primary_seed_17', primary['validation']), ('mean_seeds', chosen['summary']['mean'])]}
    for replica in chosen['replicas']:
        shutil.copyfile(output / replica['checkpoint'], output / f'selected_seed_{replica["seed"]}.pt')
    record = {'status': 'development_artifact_only', 'selected': chosen, 'primary_seed': 17, 'ensemble': False,
              'features': list(batches['train'].features), 'input_shape': list(batches['train'].x.shape[1:]),
              'train_window_ids': list(batches['train'].window_ids), 'validation_window_ids': list(batches['validation'].window_ids),
              'validation_error_gates': gates, 'model_qualified': False, 'final_test': 'locked', 'trials': trials}
    write_json(output / 'case.json', record)
    emit(f'  Selected setting {chosen["trial_index"]}; mean validation MAE={chosen["summary"]["mean"]["mae_mgL"]}; primary seed=17')
    return record, forecasts_by_trial[chosen['trial_index']]


def run_gru(config_path, settings_path, output, repository=None, matrix=False, dry_run=False):
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
    print('Verifying frozen GRU development inputs; calibration and test remain locked.', flush=True)
    release = PreparedRelease(descriptor, repository)
    criteria_path, policy_path = release.root / 'policies/release-criteria.json', release.root / 'policies/evaluation-policy.json'
    criteria, policy = [json.loads(p.read_text(encoding='utf-8')) for p in [criteria_path, policy_path]]
    validate_settings(settings, criteria, policy)
    cases = ([(c, h) for c in release.contract['input_configurations'] for h in release.contract['horizons_hours']]
             if matrix else [(config['configuration'], config['horizon_hours'])])
    prepared = []
    for configuration, horizon in cases:
        # Preserve canonical target precision for validation selection; tensors are explicitly float32 inside the fit.
        batches = {name: release.development(name, configuration, horizon, dtype=np.float64) for name in ['train', 'validation']}
        contexts = {name: release.baseline_context(name, configuration, horizon) for name in batches}
        if any(tuple(contexts[name][1].window_id) != batch.window_ids for name, batch in batches.items()):
            raise ValueError('Model arrays and evaluation windows are not aligned')
        print(f'{configuration} +{horizon}h: train={len(batches["train"].y)}, validation={len(batches["validation"].y)}; 4 settings x 3 seeds', flush=True)
        prepared.append((configuration, horizon, batches, contexts))
    device = None
    if not dry_run:
        prepare_randomness(17, 'cuda:0')
        device = check_device('cuda')
        import torch
        device.update({'cudnn_version': torch.backends.cudnn.version(), 'torch_cpu_threads': torch.get_num_threads(),
                       'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
                       'cublas_workspace_config': os.environ['CUBLAS_WORKSPACE_CONFIG'], 'float32_training': True,
                       'cudnn_benchmark': torch.backends.cudnn.benchmark, 'tf32': False,
                       'environment_packages': dict(sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions()))})
        print('Verified CUDA execution:', device, flush=True)
    report = capture_provenance(config_path, config, repository, release)
    report.update({'status': 'gru_plan_verified' if dry_run else 'running', 'matrix': matrix, 'runtime': device,
                   'settings': settings, 'settings_sha256': digest(settings_path), 'criteria_sha256': digest(criteria_path),
                   'evaluation_policy_sha256': digest(policy_path), 'seeds': [17, 29, 43], 'primary_seed': 17,
                   'model_qualified': False, 'training_performed': False, 'training_attempted': not dry_run,
                   'learned_transform_fitted': False, 'prediction_scores_computed': False,
                   'locked_partitions': ['calibration', 'test'], 'cases': [],
                   'planned_cases': [{'configuration': c, 'horizon_hours': h, 'partitions': {n: b.summary() for n, b in batches.items()}}
                                     for c, h, batches, _ in prepared]})
    output.mkdir(parents=True)
    for name, content in [('config.json', config_bytes), ('settings.json', settings_bytes), ('prepared-release.json', descriptor.read_bytes())]:
        (output / name).write_bytes(content)
    write_json(output / 'run.json', report)
    all_predictions, all_metrics = [], []
    with (output / 'progress.log').open('w', encoding='utf-8') as log:
        def emit(message):
            print(message, flush=True)
            log.write(message + '\n')
            log.flush()
        if dry_run:
            emit('Dry run verified. No torch/CUDA required and no fitting, thresholds or scoring performed.')
        else:
            training = release.training_observations()
            if len(training) != 100:
                raise ValueError('Expected 100 distinct training bins')
            threshold = lower_do_threshold(training)
            report['lower_do_diagnostic'] = {'threshold_mgL': threshold, 'fit_partition': 'train', 'distinct_observations': 100}
            for number, (configuration, horizon, batches, contexts) in enumerate(prepared, 1):
                emit(f'[{number}/{len(prepared)}] {configuration} +{horizon}h')
                path = output / configuration / f'horizon_{horizon}'
                case, forecasts = train_case(batches, contexts, settings, criteria, policy, path, emit)
                report['cases'].append({'configuration': configuration, 'horizon_hours': horizon, **case})
                report['training_performed'] = report['training_performed'] or any(r['status'] == 'ok' for t in case['trials'] for r in t['replicas'])
                report['learned_transform_fitted'] = report['training_performed']
                report['prediction_scores_computed'] = report['training_performed']
                write_json(output / 'run.json', report)
                if forecasts is not None:
                    for seed, partitions in forecasts.items():
                        for name, (observations, index) in contexts.items():
                            predictions = {b: predict_references(observations, index, b) for b in policy['baseline_candidates']}
                            predictions['gru'] = partitions[name]
                            details, metrics = evaluate_predictions(observations, index, predictions, threshold, policy)
                            all_predictions.append(details.assign(seed=seed))
                            all_metrics.extend([{**m, 'seed': seed} for m in metrics])
            if all_predictions:
                pd.concat(all_predictions, ignore_index=True).to_csv(output / 'predictions.csv', index=False)
                pd.DataFrame(all_metrics).to_csv(output / 'metrics.csv', index=False)
                write_json(output / 'metrics.json', all_metrics)
            report['status'] = 'development_gru_completed' if all(c['selected'] is not None for c in report['cases']) else 'development_gru_incomplete'
    if config_path.read_bytes() != config_bytes or settings_path.read_bytes() != settings_bytes:
        raise ValueError('Experiment configuration changed during the run')
    report['outputs_sha256'] = {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob('*')) if p.is_file() and p != output / 'run.json'}
    write_json(output / 'run.json', report)
    print('Saved', output, '; development-only models; no calibration/final-test evaluation.', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('ml/training/configs/do_pilot.json'))
    parser.add_argument('--settings', type=Path, default=Path('ml/training/configs/gru_settings.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--matrix', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        run_gru(args.config, args.settings, args.output, matrix=args.matrix, dry_run=args.dry_run)
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError, TimeoutError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
