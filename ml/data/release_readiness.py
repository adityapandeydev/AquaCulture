"""Audit historical-input readiness against provisional pilot criteria; no inference."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .aggregation import POLICY as AGGREGATION
from .eligibility import digest


QUALITY_FIELDS = ['covered_minutes', 'valid_rows', 'invalid_rows', 'maximum_gap_seconds', 'end_age_seconds']


def check_history(history, configuration, issue_time, requested_at, policy):
    """Check historical inputs only. Ready inputs do not qualify a model or forecast."""
    reasons = []

    def result():
        return {'inputs_ready': not reasons, 'reasons': sorted(set(reasons))}

    if configuration not in policy['inputs']:
        reasons.append('unsupported_configuration')
        return result()
    try:
        issue, request = pd.Timestamp(issue_time), pd.Timestamp(requested_at)
        if pd.isna(issue) or pd.isna(request) or issue.tzinfo is None or request.tzinfo is None or issue != issue.floor('h'):
            raise ValueError('Invalid availability time')
    except (TypeError, ValueError):
        reasons.append('invalid_issue_time')
        return result()
    delay = (request - issue).total_seconds()
    if delay < 0:
        reasons.append('issue_not_available')
    if delay > policy['maximum_new_issue_delay_seconds']:
        reasons.append('stale_issue')
    limits = policy['history_requirements']
    if len(history) != limits['hours']:
        reasons.append('insufficient_history' if len(history) < limits['hours'] else 'unexpected_history_length')
        return result()
    columns = policy['inputs'][configuration]
    required = {'observation_id', 'available_at', 'partition', 'preparation_imputed'} | set(policy['supported_context'])
    for column in columns:
        required.update([column, column + '_eligible'] + [column + '_' + suffix for suffix in QUALITY_FIELDS])
    if not required <= set(history.columns):
        reasons.append('missing_metadata')
        return result()
    for key, expected in policy['supported_context'].items():
        if history[key].isna().any() or not history[key].eq(expected).all():
            reasons.append('unsupported_context')
    if history.partition.isna().any() or history.partition.nunique() != 1:
        reasons.append('cross_partition_history')
    if history.observation_id.isna().any() or history.observation_id.duplicated().any():
        reasons.append('duplicate_observation')
    if history.preparation_imputed.isna().any() or not history.preparation_imputed.eq(False).all():
        reasons.append('imputed_history')
    try:
        if history.available_at.dt.tz is None or history.available_at.isna().any():
            raise ValueError('Unknown history time basis')
        expected = pd.date_range(end=issue, periods=limits['hours'], freq='h')
        if list(history.available_at) != list(expected):
            reasons.append('history_time_mismatch')
    except (AttributeError, TypeError, ValueError):
        reasons.append('invalid_history_times')
    for column in columns:
        numeric = pd.to_numeric(history[column], errors='coerce').to_numpy(dtype=float, na_value=np.nan)
        lower, upper = {'do_mgL': (0, np.inf), 'temperature_c': (-3, 60), 'ph': (0, 14)}[column]
        eligible = history[column + '_eligible']
        if (not np.isfinite(numeric).all() or not ((numeric >= lower) & (numeric <= upper)).all()
                or eligible.isna().any() or not eligible.eq(True).all()):
            reasons.append('invalid_required_measurement')
        quality = history[[column + '_' + suffix for suffix in QUALITY_FIELDS]].apply(pd.to_numeric, errors='coerce')
        quality.columns = QUALITY_FIELDS
        if not np.isfinite(quality.to_numpy(dtype=float, na_value=np.nan)).all() or (quality < 0).any().any():
            reasons.append('invalid_quality_metadata')
            continue
        if (quality.covered_minutes < limits['minimum_covered_minutes']).any() or quality.covered_minutes.gt(60).any():
            reasons.append('insufficient_coverage')
        if quality.valid_rows.lt(quality.covered_minutes * limits['minimum_readings_per_minute']).any():
            reasons.append('insufficient_readings')
        if quality.maximum_gap_seconds.gt(limits['maximum_gap_seconds']).any():
            reasons.append('gap_exceeded')
        if quality.end_age_seconds.gt(limits['maximum_end_age_seconds']).any():
            reasons.append('sensor_stale')
        if quality.end_age_seconds.iloc[-1] + max(delay, 0) > policy['maximum_latest_raw_age_at_request_seconds']:
            reasons.append('latest_observation_stale_at_request')
    return result()


def run(evaluation, policy_path, output):
    if output.exists():
        raise FileExistsError(output)
    manifest_path = evaluation / 'evaluation_manifest.json'
    evaluation_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    expected_requirements = {'hours': 6, 'minimum_readings_per_minute': AGGREGATION['minimum_readings_per_minute'],
                             'minimum_covered_minutes': AGGREGATION['minimum_covered_minutes'],
                             'maximum_gap_seconds': AGGREGATION['maximum_gap_seconds_including_edges'],
                             'maximum_end_age_seconds': AGGREGATION['maximum_end_age_seconds']}
    if (policy['evaluation_policy_version'] != evaluation_manifest['version']
            or policy['history_requirements'] != expected_requirements
            or policy['interval_release_status'] != evaluation_manifest['policy']['interval_release_status']
            or policy['training_approved'] or policy['model_qualification'] != 'not_assessed_no_new_model_results'):
        raise ValueError('Criteria differ from reviewed pilot scope or imply premature qualification')
    for limits in policy['accuracy_limits_by_horizon_hours'].values():
        if any(value <= 0 for value in limits.values()) or limits['maximum_rmse_mgL'] < limits['maximum_mae_mgL']:
            raise ValueError('Invalid accuracy limits')
    horizons = [evaluation_manifest['policy']['primary_horizon_hours']] + evaluation_manifest['policy']['secondary_horizon_hours']
    if (set(policy['accuracy_limits_by_horizon_hours']) != {str(h) for h in horizons}
            or policy['minimum_prediction_coverage'] != 1.0
            or not 0 < policy['minimum_mae_skill_vs_persistence'] <= 1):
        raise ValueError('Missing horizon gates, incomplete-coverage allowance or invalid improvement target')
    if any(value <= 0 for value in policy['cpu_resource_limits'].values()):
        raise ValueError('Resource limits must be positive')
    inputs = {str(manifest_path): digest(manifest_path), str(policy_path): digest(policy_path)}
    inputs.update(evaluation_manifest['inputs_sha256'])
    for name, expected in evaluation_manifest['outputs_sha256'].items():
        inputs[str(evaluation / name)] = expected
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError('Reviewed artifact changed: ' + path)
    supervised_paths = [Path(p) for p in inputs if Path(p).name == 'supervised_manifest.json']
    if len(supervised_paths) != 1:
        raise ValueError('Exactly one supervised manifest required')
    supervised = json.loads(supervised_paths[0].read_text(encoding='utf-8'))
    if policy['supervised_contract_version'] != supervised['version'] or policy['inputs'] != supervised['contract']['input_configurations']:
        raise ValueError('Input configurations differ from supervised contract')
    observation_paths = [Path(p) for p in inputs if Path(p).name == 'observations.csv.gz']
    if len(observation_paths) != 1:
        raise ValueError('Exactly one reviewed observation table required')
    observations = pd.read_csv(observation_paths[0])
    observations['available_at'] = pd.to_datetime(observations.available_at, utc=True)
    rows = []
    for (session, partition), group in observations.groupby(['session_id', 'partition']):
        group = group.sort_values('available_at')
        for issue in group.available_at:
            history = group[group.available_at.le(issue)].tail(policy['history_requirements']['hours'])
            for configuration in policy['inputs']:
                checked = check_history(history, configuration, issue, issue, policy)
                rows.append({'session_id': session, 'partition': partition, 'configuration': configuration,
                             'issue_time': issue.isoformat(), 'historical_bins': len(history),
                             'inputs_ready': checked['inputs_ready'], 'reasons': json.dumps(checked['reasons'])})
    frame = pd.DataFrame(rows)
    counts = frame.groupby(['partition', 'configuration']).agg(issue_rows=('inputs_ready', 'size'),
                                                               ready_issues=('inputs_ready', 'sum')).reset_index()
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError('Input changed during readiness audit: ' + path)
    output.mkdir(parents=True)
    frame.to_csv(output / 'readiness_index.csv', index=False)
    counts.to_csv(output / 'readiness_counts.csv', index=False)
    report = {'version': policy['version'], 'policy': policy, 'training_approved': False,
              'model_qualification': policy['model_qualification'], 'simulation': 'Historical new-issue request at exactly bin end; no future target checks or real delay measurements.',
              'inputs_sha256': inputs, 'outputs_sha256': {p.name: digest(p) for p in sorted(output.iterdir())},
              'issue_configuration_rows': len(frame), 'inputs_ready_rows': int(frame.inputs_ready.sum()),
              'counts': counts.to_dict('records'), 'predictions_or_scores_computed': False,
              'resource_measurements': 'not_performed_no_new_model_artifact'}
    (output / 'criteria_manifest.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(counts.to_string(index=False))
    print('Input-ready rows:', int(frame.inputs_ready.sum()), 'of', len(frame), '; model qualification not assessed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', type=Path, default=Path('Datasets/processed/oman-evaluation-plan-2026-11-07'))
    parser.add_argument('--policy', type=Path, default=Path('docs/data/release-criteria.json'))
    parser.add_argument('--output', type=Path, default=Path('Datasets/processed/oman-criteria-2026-11-07-v2'))
    args = parser.parse_args()
    run(args.evaluation, args.policy, args.output)
