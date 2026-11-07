"""Freeze observation-disjoint chronological periods for the Oman tank pilot."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .eligibility import count_examples, digest
from .lineage import validate_partition_claim


def assert_disjoint(frame, identity_columns):
    if frame[identity_columns + ['partition']].isna().any().any():
        raise ValueError('Missing observation identity or partition')
    if frame.groupby(identity_columns).partition.nunique().gt(1).any():
        raise ValueError('An observation identity crosses partition boundaries')


def assign_bins(frame, policy):
    """Assign complete half-open hourly bins, not just their end timestamps."""
    bins = frame.sort_values('available_at').reset_index(drop=True).copy()
    if bins.empty or bins.session_id.nunique() != 1 or not bins.session_id.eq(policy['session_id']).all():
        raise ValueError('Only the selected session may enter the split')
    if bins.available_at.isna().any() or bins.available_at.dt.tz is None:
        raise ValueError('Timezone-aware nonmissing availability times required')
    if bins.duplicated(['session_id', 'available_at']).any():
        raise ValueError('Duplicate hourly observation')
    if not bins.available_at.eq(bins.available_at.dt.floor('h')).all():
        raise ValueError('Hourly boundaries required')
    bins['bin_start'] = bins.available_at - pd.Timedelta(hours=1)
    bins['partition'] = ''
    previous, names = None, set()
    for period in policy['partitions']:
        start, end = pd.Timestamp(period['start_utc']), pd.Timestamp(period['end_utc'])
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            raise ValueError('Positive timezone-aware period required')
        if start != start.floor('h') or end != end.floor('h'):
            raise ValueError('Period boundaries must align to hours')
        if period['name'] in names or (previous is not None and start != previous):
            raise ValueError('Periods must be unique, ordered and adjacent')
        if (end - start) != pd.Timedelta(hours=period['hours']):
            raise ValueError('Period duration differs from policy')
        mask = bins.bin_start.ge(start) & bins.available_at.le(end)
        expected = pd.date_range(start + pd.Timedelta(hours=1), end, freq='h')
        if list(bins.loc[mask, 'available_at']) != list(expected):
            raise ValueError('Missing or extra hourly support in frozen period')
        bins.loc[mask, 'partition'] = period['name']
        previous = end
        names.add(period['name'])
    if bins.partition.eq('').any():
        raise ValueError('Hourly observations outside frozen periods')
    assert_disjoint(bins, ['session_id', 'available_at'])
    return bins


def map_parents(rows, bins, source_hash):
    parents = rows.copy()
    parents['available_at'] = parents.timestamp_utc.dt.floor('h') + pd.Timedelta(hours=1)
    parents = parents.merge(bins[['session_id', 'available_at', 'partition']],
                            on=['session_id', 'available_at'], how='inner', validate='many_to_one')
    parents['source_sha256'] = source_hash
    if parents.duplicated(['source_sha256', 'source_row']).any():
        raise ValueError('Repeated raw observation parent')
    assert_disjoint(parents, ['source_sha256', 'source_row'])
    return parents[['source_sha256', 'source_row', 'session_id', 'timestamp_utc', 'available_at', 'partition']]


def split_counts(inputs, targets, bins, history, horizon):
    keys = ['session_id', 'available_at']
    tables = []
    for frame in [inputs, targets]:
        mapped = frame.merge(bins[keys + ['partition']], on=keys, how='left', validate='one_to_one')
        if mapped.partition.isna().any():
            raise ValueError('Unassigned input or target observation')
        tables.append(mapped)
    result = {}
    for name in bins.partition.unique():
        historical = tables[0][tables[0].partition.eq(name)]
        future = tables[1][tables[1].partition.eq(name)]
        result[name] = sum(count_examples(historical, future, history, horizon).values())
    return result


def run(prepared, sessions, eligibility_path, selection_path, policy_path, lineage_path, output):
    if output.exists():
        raise FileExistsError(output)
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    lineage = json.loads(lineage_path.read_text(encoding='utf-8'))
    source = next(s for s in lineage['sources'] if s['source_id'] == policy['source_id'])
    if (selection['version'] != policy['release_selection_version']
            or selection['session_roles'].get(policy['session_id']) != 'primary_tank_pilot'
            or selection['source_id'] != policy['source_id']
            or source['lineage_group_id'] != policy['lineage_group_id']):
        raise ValueError('Unreviewed source, session, lineage or selection')
    if policy['evaluation_claim'] != 'chronological_within_study' or policy['independent_site_verified']:
        raise ValueError('No independent-site evidence exists for this pilot')
    validate_partition_claim({policy['lineage_group_id']}, {policy['lineage_group_id']}, policy['evaluation_claim'])
    if [p['name'] for p in policy['partitions']] != ['train', 'validation', 'calibration', 'test']:
        raise ValueError('Four ordered periods required')
    if policy['history_hours'] != selection['primary_history_hours']:
        raise ValueError('History differs from selected task')
    if policy['horizons_hours'] != [selection['primary_horizon_hours']] + selection['secondary_horizon_hours']:
        raise ValueError('Horizons differ from selected task')
    if policy['input_configurations'] != selection['input_configurations'] or policy['training_approved']:
        raise ValueError('Unreviewed configuration or premature training approval')
    files = [prepared / 'hourly_channels.csv.gz', prepared / 'hourly_configurations.csv',
             prepared / 'aggregation.json', sessions / 'inventory.json',
             sessions / f"{policy['recording']}_timestamp_rows.csv.gz", selection_path, policy_path, lineage_path, eligibility_path]
    inputs = {str(path): digest(path) for path in files}
    eligibility = json.loads(eligibility_path.read_text(encoding='utf-8'))
    for reviewed in files[:3] + [selection_path]:
        if eligibility['inputs_sha256'].get(str(reviewed)) != inputs[str(reviewed)]:
            raise ValueError('Prepared data or selection changed since eligibility review: ' + str(reviewed))
    aggregation = json.loads(files[2].read_text(encoding='utf-8'))
    if aggregation['policy']['version'] != policy['aggregation_policy_version']:
        raise ValueError('Aggregation policy mismatch')
    for path, expected in aggregation['inputs_sha256'].items():
        if digest(Path(path)) != expected:
            raise ValueError('Upstream input changed: ' + path)
        inputs[path] = expected
    inventory = json.loads(files[3].read_text(encoding='utf-8'))
    if inventory['recordings'][policy['recording']]['source_sha256'] != policy['source_sha256']:
        raise ValueError('Selected raw source changed')
    configs, channels, raw_rows = pd.read_csv(files[1]), pd.read_csv(files[0]), pd.read_csv(files[4])
    for frame in [configs, channels]:
        frame['available_at'] = pd.to_datetime(frame.available_at, utc=True)
    raw_rows['timestamp_utc'] = pd.to_datetime(raw_rows.timestamp_utc, utc=True)
    selected = configs[configs.session_id.eq(policy['session_id']) & configs.candidate_eligible].copy()
    reference = selected[selected.configuration.eq('do_only')]
    bins = assign_bins(reference[['session_id', 'available_at', 'candidate_eligible']], policy)
    namespace = '|'.join([policy['source_sha256'], policy['session_id'], policy['aggregation_policy_version']])
    bins['observation_id'] = [hashlib.sha256((namespace + '|' + t.isoformat()).encode()).hexdigest() for t in bins.available_at]
    selected_keys = bins[['session_id', 'available_at']]
    target = channels[channels.session_id.eq(policy['session_id']) & channels.channel.eq('do')].merge(
        selected_keys, on=['session_id', 'available_at'], validate='one_to_one')
    if not target.candidate_eligible.all() or len(target) != len(bins):
        raise ValueError('Selected targets lack hourly quality support')
    rows = raw_rows[raw_rows.session_id.eq(policy['session_id'])].copy()
    if rows.model_use.str.startswith('excluded').any():
        raise ValueError('Excluded session in fitting release')
    parents = map_parents(rows, bins, policy['source_sha256'])
    expected_parents = rows[rows.timestamp_utc.ge(bins.bin_start.min()) & rows.timestamp_utc.lt(bins.available_at.max())]
    if len(parents) != len(expected_parents) or parents.available_at.nunique() != len(bins):
        raise ValueError('Raw-parent accounting or hourly support failed')
    counts, losses = [], []
    for configuration in policy['input_configurations']:
        historical = selected[selected.configuration.eq(configuration)]
        if set(historical.available_at) != set(bins.available_at) or len(historical) != len(bins):
            raise ValueError('Input configurations do not have paired complete support')
        for horizon in policy['horizons_hours']:
            result = split_counts(historical, target, bins, policy['history_hours'], horizon)
            for name, count in result.items():
                if count == 0:
                    raise ValueError('Frozen task has an empty partition')
                counts.append({'partition': name, 'configuration': configuration, 'history_hours': policy['history_hours'],
                               'horizon_hours': horizon, 'examples': count})
            total = sum(count_examples(historical, target, policy['history_hours'], horizon).values())
            losses.append({'configuration': configuration, 'horizon_hours': horizon, 'pre_split_examples': total,
                           'partitioned_examples': sum(result.values()), 'boundary_rejected_examples': total - sum(result.values())})
    assert_disjoint(bins, ['observation_id'])
    for path, expected in inputs.items():
        if digest(Path(path)) != expected:
            raise ValueError('Input changed during split freeze: ' + path)
    output.mkdir(parents=True)
    bins.to_csv(output / 'observation_partitions.csv', index=False)
    parents.to_csv(output / 'raw_parent_partitions.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    pd.DataFrame(counts).to_csv(output / 'split_counts.csv', index=False)
    report = {'version': policy['version'], 'policy': policy, 'training_approved': False,
              'inputs_sha256': inputs, 'outputs_sha256': {p.name: digest(p) for p in sorted(output.iterdir())},
              'hourly_observations': len(bins), 'raw_parents': len(parents),
              'counts': counts, 'boundary_losses': losses,
              'raw_parent_counts': {str(k): int(v) for k, v in parents.partition.value_counts().items()},
              'checks': {'unique_hourly_ids': True, 'disjoint_raw_parent_identities': True,
                         'disjoint_possible_target_observations': True, 'complete_partition_containment': True,
                         'same_study_lineage_disclosed': True, 'nonempty_structural_example_counts': True},
              'statistical_sufficiency': policy['statistical_sufficiency'],
              'interval_release_status': policy['interval_release_status']}
    (output / 'split_manifest.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(pd.DataFrame(counts).to_string(index=False))
    print('Hourly observations:', len(bins), '; disjoint raw parents:', len(parents))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, default=Path('Datasets/processed/oman-aggregation-2026-11-05'))
    parser.add_argument('--sessions', type=Path, default=Path('Datasets/processed/oman-sessions-2026-11-05-v2'))
    parser.add_argument('--eligibility', type=Path, default=Path('Datasets/processed/oman-eligibility-2026-11-05/eligibility.json'))
    parser.add_argument('--selection', type=Path, default=Path('docs/data/release-selection.json'))
    parser.add_argument('--policy', type=Path, default=Path('docs/data/partition-policy.json'))
    parser.add_argument('--lineage', type=Path, default=Path('docs/data/lineage-policy.json'))
    parser.add_argument('--output', type=Path, default=Path('Datasets/processed/oman-partitions-2026-11-07-v2'))
    args = parser.parse_args()
    run(args.prepared, args.sessions, args.eligibility, args.selection, args.policy, args.lineage, args.output)
