"""Export supervised observation references without fitting a model or transform."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .eligibility import digest
from .partitions import assert_disjoint


CHANNELS = {'do': 'do_mgL', 'temperature': 'temperature_c', 'ph': 'ph'}
QUALITY_METADATA = ['covered_minutes', 'valid_rows', 'invalid_rows', 'end_age_seconds',
                    'maximum_gap_seconds', 'zero_review_rows', 'rapid_change_review_rows']


def identity(*parts):
    return hashlib.sha256(json.dumps(parts, separators=(',', ':')).encode()).hexdigest()


def check_observations(observations, contract):
    if observations.observation_id.isna().any() or observations.observation_id.duplicated().any():
        raise ValueError('Unique observation IDs required')
    if observations.duplicated(['session_id', 'available_at']).any():
        raise ValueError('Duplicate session/time observation')
    if observations[['session_id', 'partition', 'available_at']].isna().any().any():
        raise ValueError('Missing temporal or grouping identity')
    if observations.available_at.dt.tz is None or not observations.available_at.eq(observations.available_at.dt.floor('h')).all():
        raise ValueError('Timezone-aware hourly availability required')
    if type(contract['history_hours']) is not int or contract['history_hours'] < 1:
        raise ValueError('Positive integer history required')
    if not contract['horizons_hours'] or any(type(h) is not int or h < 1 for h in contract['horizons_hours']):
        raise ValueError('Positive integer horizons required')
    if len(set(contract['horizons_hours'])) != len(contract['horizons_hours']):
        raise ValueError('Duplicate horizons')
    for columns in contract['input_configurations'].values():
        if not columns or len(set(columns)) != len(columns) or not set(columns) <= set(CHANNELS.values()):
            raise ValueError('Only explicitly ordered water-measurement features are permitted')


def supported(frame, columns):
    if 'preparation_imputed' in frame and not frame.preparation_imputed.eq(False).all():
        return False
    return all(frame[column + '_eligible'].eq(True).all() and np.isfinite(frame[column].to_numpy(dtype=float)).all()
               for column in columns)


def validate_window(observations, window, contract):
    """Validate explicit references, times, grouping, required measurements and labels."""
    check_observations(observations, contract)
    configuration = window['configuration']
    if configuration not in contract['input_configurations'] or window['horizon_hours'] not in contract['horizons_hours']:
        raise ValueError('Unsupported configuration or horizon')
    lookup = observations.set_index('observation_id')
    ids = window['input_observation_ids'] + window['future_do_observation_ids']
    if len(set(ids)) != len(ids) or not set(ids) <= set(lookup.index):
        raise ValueError('Repeated or missing window observation reference')
    history = lookup.loc[window['input_observation_ids']]
    future = lookup.loc[window['future_do_observation_ids']]
    issue = pd.Timestamp(window['issue_time'])
    horizon = window['horizon_hours']
    expected_history = pd.date_range(end=issue, periods=contract['history_hours'], freq='h')
    expected_future = pd.date_range(start=issue + pd.Timedelta(hours=1), periods=horizon, freq='h')
    if list(history.available_at) != list(expected_history) or list(future.available_at) != list(expected_future):
        raise ValueError('Window has unavailable inputs, gaps or incorrect target alignment')
    for frame in [history, future]:
        if not frame.partition.eq(window['partition']).all() or not frame.session_id.eq(window['session_id']).all():
            raise ValueError('Window crosses partition or session boundary')
    if not supported(history, contract['input_configurations'][configuration]) or not supported(future, ['do_mgL']):
        raise ValueError('Missing or invalid required input/target measurements')
    if window['target_observation_id'] != future.index[-1] or pd.Timestamp(window['target_available_at']) != expected_future[-1]:
        raise ValueError('Incorrect target identity or availability')
    if pd.Timestamp(window['target_interval_start']) != expected_future[-1] - pd.Timedelta(hours=1):
        raise ValueError('Incorrect target interval start')
    if pd.Timestamp(window['target_interval_end']) != expected_future[-1]:
        raise ValueError('Incorrect target interval end')


def input_matrix(observations, window, contract):
    """Resolve this preparation index's historical values in the declared feature order."""
    validate_window(observations, window, contract)
    columns = contract['input_configurations'][window['configuration']]
    return observations.set_index('observation_id').loc[window['input_observation_ids'], columns].to_numpy(dtype=float)


def build_windows(observations, contract):
    check_observations(observations, contract)
    windows = []
    for (session, partition), group in observations.groupby(['session_id', 'partition'], sort=True):
        group = group.sort_values('available_at').set_index('available_at', drop=False)
        available = set(group.index)
        for configuration, columns in contract['input_configurations'].items():
            for issue in group.index:
                history_times = pd.date_range(end=issue, periods=contract['history_hours'], freq='h')
                if not set(history_times) <= available or not supported(group.loc[history_times], columns):
                    continue
                history_ids = group.loc[history_times, 'observation_id'].tolist()
                for horizon in contract['horizons_hours']:
                    future_times = pd.date_range(start=issue + pd.Timedelta(hours=1), periods=horizon, freq='h')
                    if not set(future_times) <= available or not supported(group.loc[future_times], ['do_mgL']):
                        continue
                    future_ids = group.loc[future_times, 'observation_id'].tolist()
                    windows.append({
                        'window_id': identity(contract['version'], configuration, history_ids, future_ids, partition, session),
                        'comparison_id': identity(contract['version'], session, partition, issue.isoformat(), horizon),
                        'session_id': session, 'partition': partition, 'configuration': configuration,
                        'issue_time': issue.isoformat(), 'horizon_hours': horizon,
                        'input_observation_ids': history_ids, 'future_do_observation_ids': future_ids,
                        'target_observation_id': future_ids[-1], 'target_available_at': future_times[-1].isoformat(),
                        'target_interval_start': (future_times[-1] - pd.Timedelta(hours=1)).isoformat(),
                        'target_interval_end': future_times[-1].isoformat()})
    return windows


def paired_issues(windows, contract):
    groups = {}
    for window in windows:
        key = tuple(window[field] for field in ['session_id', 'partition', 'configuration', 'issue_time'])
        horizons = groups.setdefault(key, {})
        if str(window['horizon_hours']) in horizons:
            raise ValueError('Duplicate horizon at one issue')
        horizons[str(window['horizon_hours'])] = window['window_id']
    pairs = []
    for (session, partition, configuration, issue), horizons in sorted(groups.items()):
        if set(horizons) == {str(h) for h in contract['horizons_hours']}:
            pairs.append({'issue_id': identity(contract['version'], session, partition, configuration, issue),
                          'session_id': session, 'partition': partition, 'configuration': configuration,
                          'issue_time': issue, 'window_ids_by_horizon': horizons})
    return pairs


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n' for row in rows), encoding='utf-8')


def run(partitions, contract_path, output):
    if output.exists():
        raise FileExistsError(output)
    manifest_path = partitions / 'split_manifest.json'
    freeze = json.loads(manifest_path.read_text(encoding='utf-8'))
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    policy = freeze['policy']
    if (contract['partition_policy_version'] != freeze['version']
            or contract['aggregation_policy_version'] != policy['aggregation_policy_version']
            or contract['history_hours'] != policy['history_hours']
            or contract['horizons_hours'] != policy['horizons_hours']
            or list(contract['input_configurations']) != policy['input_configurations']
            or contract['input_configurations'] != {'do_only': ['do_mgL'], 'do_temperature_ph': list(CHANNELS.values())}
            or contract['cadence_seconds'] != 3600 or contract['quality_metadata_suffixes'] != QUALITY_METADATA
            or contract['units'] != {'do_mgL': 'mg/L', 'temperature_c': 'degC', 'ph': 'pH'}
            or contract['target']['column'] != 'do_mgL' or contract['target']['preparation_imputed']
            or contract['target']['unit'] != 'mg/L' or contract['target']['statistic'] != 'mean_of_covered_minute_medians'
            or contract['target']['value_kind'] != 'aggregate_of_source_reported_measurements'
            or contract['training_approved'] or freeze['training_approved']):
        raise ValueError('Supervised contract differs from reviewed task/partition scope')
    inputs = {str(manifest_path): digest(manifest_path), str(contract_path): digest(contract_path)}
    for name, expected in freeze['outputs_sha256'].items():
        inputs[str(partitions / name)] = expected
    inputs.update(freeze['inputs_sha256'])
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError('Frozen input or partition artifact changed: ' + path)
    bins = pd.read_csv(partitions / 'observation_partitions.csv')
    bins['available_at'] = pd.to_datetime(bins.available_at, utc=True)
    channel_paths = [Path(p) for p in inputs if Path(p).name == 'hourly_channels.csv.gz']
    if len(channel_paths) != 1:
        raise ValueError('Exactly one reviewed hourly-channel artifact is required')
    channels = pd.read_csv(channel_paths[0])
    channels['available_at'] = pd.to_datetime(channels.available_at, utc=True)
    observations = bins.set_index('observation_id')
    for parameter, column in CHANNELS.items():
        measured = channels[channels.channel.eq(parameter)].merge(
            bins[['session_id', 'available_at', 'observation_id']], on=['session_id', 'available_at'], validate='one_to_one')
        if len(measured) != len(bins):
            raise ValueError('Missing frozen channel support')
        measured = measured.set_index('observation_id').reindex(observations.index)
        observations[column] = measured.value
        observations[column + '_eligible'] = measured.candidate_eligible
        for suffix in QUALITY_METADATA:
            observations[column + '_' + suffix] = measured[suffix]
    observations = observations.reset_index()
    observations['source_sha256'] = policy['source_sha256']
    observations['lineage_group_id'] = policy['lineage_group_id']
    observations['value_kind'] = contract['target']['value_kind']
    observations['preparation_imputed'] = False
    windows = build_windows(observations, contract)
    for window in windows:
        validate_window(observations, window, contract)
    frame = pd.DataFrame(windows)
    if frame.window_id.duplicated().any():
        raise ValueError('Duplicate window ID')
    counts = frame.groupby(['partition', 'configuration', 'horizon_hours']).size().rename('examples').reset_index()
    expected = pd.read_csv(partitions / 'split_counts.csv')
    compared = expected.merge(counts, on=['partition', 'configuration', 'horizon_hours'], how='outer', suffixes=('_expected', '_actual'), validate='one_to_one')
    if not compared.examples_expected.eq(compared.examples_actual).all():
        raise ValueError('Window counts differ from frozen feasibility counts')
    targets = frame[['target_observation_id', 'partition']].drop_duplicates()
    assert_disjoint(targets, ['target_observation_id'])
    # Configuration comparisons must refer to identical issues and labels in this release.
    for _, group in frame.groupby('comparison_id'):
        if set(group.configuration) != set(contract['input_configurations']) or group.target_observation_id.nunique() != 1:
            raise ValueError('Unpaired configuration comparison')
    pairs = paired_issues(windows, contract)
    paired_counts = pd.DataFrame(pairs).groupby(['partition', 'configuration']).size().rename('common_issues').reset_index()
    for path, expected_hash in inputs.items():
        if digest(Path(path)) != expected_hash:
            raise ValueError('Input changed during supervised export: ' + path)
    output.mkdir(parents=True)
    observations.to_csv(output / 'observations.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    write_jsonl(output / 'windows.jsonl', windows)
    write_jsonl(output / 'paired_issues.jsonl', pairs)
    counts.to_csv(output / 'window_counts.csv', index=False)
    paired_counts.to_csv(output / 'paired_issue_counts.csv', index=False)
    report = {'version': contract['version'], 'contract': contract, 'partition_policy_version': freeze['version'],
              'training_approved': False, 'inputs_sha256': inputs,
              'outputs_sha256': {p.name: digest(p) for p in sorted(output.iterdir())},
              'observation_rows': len(observations), 'window_rows': len(windows), 'paired_issue_rows': len(pairs),
              'counts': counts.to_dict('records'), 'paired_counts': paired_counts.to_dict('records'),
              'checks': {'all_references_resolve': True, 'issue_time_availability': True,
                         'same_partition_session_support': True, 'target_path_continuity': True,
                         'disjoint_targets_between_partitions': True, 'paired_configuration_targets': True,
                         'counts_match_partition_freeze': True, 'no_learned_transform_fitted': True},
              'interval_release_status': freeze['interval_release_status']}
    (output / 'supervised_manifest.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('Observations:', len(observations), '; window references:', len(windows), '; joint-horizon issues:', len(pairs))
    print(paired_counts.to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partitions', type=Path, default=Path('Datasets/processed/oman-partitions-2026-11-07-v2'))
    parser.add_argument('--contract', type=Path, default=Path('docs/data/supervised-contract.json'))
    parser.add_argument('--output', type=Path, default=Path('Datasets/processed/oman-supervised-2026-11-07'))
    args = parser.parse_args()
    run(args.partitions, args.contract, args.output)
