"""Register baseline observation references and comparison cohorts; compute no forecasts."""
import argparse
import json
from pathlib import Path

import pandas as pd

from .eligibility import digest
from .windows import paired_issues, supported, validate_window


def build_plan(observations, windows, contract, seasonal_period_hours):
    if type(seasonal_period_hours) is not int or seasonal_period_hours < max(contract['horizons_hours']):
        raise ValueError('Seasonal references must be available by every issue time')
    if not windows or len({w['window_id'] for w in windows}) != len(windows):
        raise ValueError('Nonempty unique window references required')
    lookup = observations.set_index(['session_id', 'available_at'], drop=False)
    joint = {window_id for pair in paired_issues(windows, contract)
             for window_id in pair['window_ids_by_horizon'].values()}
    rows = []
    for window in windows:
        validate_window(observations, window, contract)
        issue = pd.Timestamp(window['issue_time'])
        reference_time = pd.Timestamp(window['target_available_at']) - pd.Timedelta(hours=seasonal_period_hours)
        if reference_time > issue:
            raise ValueError('Future observation would enter a seasonal baseline')
        key = (window['session_id'], reference_time)
        reference_id, available, reason = None, False, 'outside_partition_or_missing'
        if key in lookup.index:
            reference = lookup.loc[[key]]
            if reference.partition.eq(window['partition']).all():
                if supported(reference, ['do_mgL']):
                    reference_id, available, reason = reference.observation_id.iloc[0], True, 'available'
                else:
                    reason = 'ineligible_reference'
        rows.append({'window_id': window['window_id'], 'comparison_id': window['comparison_id'],
                     'session_id': window['session_id'], 'partition': window['partition'],
                     'configuration': window['configuration'], 'horizon_hours': window['horizon_hours'],
                     'issue_time': window['issue_time'], 'target_observation_id': window['target_observation_id'],
                     'persistence_reference_id': window['input_observation_ids'][-1],
                     'seasonal_reference_time': reference_time.isoformat(), 'seasonal_reference_id': reference_id,
                     'seasonal_reference_status': reason, 'all_horizon_specific': True,
                     'common_horizons': window['window_id'] in joint, 'seasonal_matched': available})
    plan = pd.DataFrame(rows)
    keys = ['session_id', 'partition', 'configuration', 'issue_time']
    all_seasonal = plan.groupby(keys).seasonal_matched.transform('all')
    plan['common_horizons_seasonal_matched'] = plan.common_horizons & all_seasonal
    return plan


def run(prepared, policy_path, output):
    if output.exists():
        raise FileExistsError(output)
    manifest_path = prepared / 'supervised_manifest.json'
    supervised = json.loads(manifest_path.read_text(encoding='utf-8'))
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    if (supervised['version'] != policy['supervised_contract_version']
            or supervised['partition_policy_version'] != policy['partition_policy_version']
            or policy['seasonal_period_hours'] != 24
            or supervised['contract']['horizons_hours'] != [policy['primary_horizon_hours']] + policy['secondary_horizon_hours']
            or policy['training_approved'] or policy['prediction_scores_computed']
            or policy['interval_release_status'] != supervised['interval_release_status']):
        raise ValueError('Evaluation policy differs from reviewed pilot scope')
    inputs = {str(manifest_path): digest(manifest_path), str(policy_path): digest(policy_path)}
    inputs.update(supervised['inputs_sha256'])
    for name, expected in supervised['outputs_sha256'].items():
        inputs[str(prepared / name)] = expected
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError('Reviewed supervised input changed: ' + path)
    observations = pd.read_csv(prepared / 'observations.csv.gz')
    observations['available_at'] = pd.to_datetime(observations.available_at, utc=True)
    windows = [json.loads(line) for line in (prepared / 'windows.jsonl').read_text(encoding='utf-8').splitlines()]
    plan = build_plan(observations, windows, supervised['contract'], policy['seasonal_period_hours'])
    if len(plan) != supervised['window_rows']:
        raise ValueError('Unexpected evaluation denominator')
    cohorts = policy['comparison_cohorts']
    counts = plan.groupby(['partition', 'configuration', 'horizon_hours'])[cohorts].sum().reset_index()
    inventory_paths = [Path(p) for p in inputs if Path(p).name == 'inventory.json']
    if len(inventory_paths) != 1:
        raise ValueError('Exactly one reviewed session inventory required')
    inventory = json.loads(inventory_paths[0].read_text(encoding='utf-8'))
    selected = [s for s in inventory['session_inventory'] if s['session_id'] in set(plan.session_id)]
    if len(selected) != 1:
        raise ValueError('Unexpected source/session grouping')
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError('Input changed during evaluation planning: ' + path)
    output.mkdir(parents=True)
    plan.to_csv(output / 'evaluation_index.csv', index=False)
    counts.to_csv(output / 'cohort_counts.csv', index=False)
    report = {'version': policy['version'], 'policy': policy, 'training_approved': False,
              'prediction_scores_computed': False, 'inputs_sha256': inputs,
              'outputs_sha256': {p.name: digest(p) for p in sorted(output.iterdir())},
              'evaluation_rows': len(plan), 'cohort_counts': counts.to_dict('records'),
              'group': {key: selected[0][key] for key in ['session_id', 'species', 'environment', 'lineage_group_id']},
              'checks': {'persistence_available_at_issue': True, 'seasonal_phase_matches_target': True,
                         'seasonal_same_partition_session': True, 'joint_horizon_cohorts_explicit': True,
                         'no_predictions_or_scores_generated': True}}
    (output / 'evaluation_manifest.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(counts.to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, default=Path('Datasets/processed/oman-supervised-2026-11-07'))
    parser.add_argument('--policy', type=Path, default=Path('docs/data/evaluation-policy.json'))
    parser.add_argument('--output', type=Path, default=Path('Datasets/processed/oman-evaluation-plan-2026-11-07'))
    args = parser.parse_args()
    run(args.prepared, args.policy, args.output)
