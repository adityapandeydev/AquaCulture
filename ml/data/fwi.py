"""Prepare hourly DO series, partitions and forecast windows from the pinned FWI campaign.

The policy in docs/data/fwi-policy.json fixes every exclusion and split before any model is
fitted. Source files are read only. Nothing is filled, smoothed or interpolated.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .eligibility import digest

COLUMNS = ['time', 'do', 'ph', 'temperature', 'flag_time', 'flag_do', 'flag_ph']
HOUR = pd.Timedelta(hours=1)


def read_pond(path):
    frame = pd.read_csv(path)
    if frame.shape[1] != len(COLUMNS) or frame.columns[0] != 'Date/Time (IST)':
        raise ValueError('Unexpected pond schema: ' + path.name)
    frame.columns = COLUMNS
    frame['time'] = pd.to_datetime(frame.time, format='%Y-%m-%d %H:%M:%S')
    for column in ['do', 'ph', 'temperature']:
        values = pd.to_numeric(frame[column], errors='coerce')
        # The publisher identifies exact zeros as equipment artifacts.
        frame[column] = values.where(np.isfinite(values) & values.gt(0))
    return frame


def excluded_rows(frame, pond, policy):
    """Mark event days, declared intervals and days dominated by a duplicated stream."""
    day = frame.time.dt.normalize()
    excluded = day.isin(pd.to_datetime(policy['event_days'][pond]))
    for item in policy['excluded_intervals']:
        if item['pond_id'] == pond:
            excluded |= frame.time.ge(item['start']) & frame.time.lt(item['end'])
    duplicated = frame.time.duplicated(keep=False)
    per_day = duplicated.groupby(day).transform('sum')
    return excluded | per_day.gt(policy['readings']['maximum_duplicate_rows_per_day'])


def hourly(frame, pond, policy):
    """Aggregate readings into local clock hours and assign device sessions."""
    rules = policy['readings']
    frame = frame.sort_values('time', kind='stable').copy()
    frame['excluded'] = excluded_rows(frame, pond, policy)
    frame['conflict'] = frame.time.duplicated(keep=False)
    frame['hour'] = frame.time.dt.floor('h')
    valid_do = frame.do.where(~frame.excluded)
    groups = frame.assign(do=valid_do).groupby('hour')
    table = groups.agg(readings=('do', 'count'), do_mgL=('do', 'mean'), do_min_mgL=('do', 'min'),
                       ph=('ph', 'mean'), ph_readings=('ph', 'count'),
                       temperature_c=('temperature', 'mean'), temperature_readings=('temperature', 'count'),
                       excluded=('excluded', 'any'), conflict=('conflict', 'any'),
                       flagged_do=('flag_do', 'count')).reset_index()
    table.insert(0, 'pond_id', pond)
    table['eligible'] = table.readings.ge(rules['minimum_per_hour']) & ~table.excluded & ~table.conflict
    for value, count in [('ph', 'ph_readings'), ('temperature_c', 'temperature_readings')]:
        table[value] = table[value].where(table.eligible & table[count].ge(rules['minimum_per_hour']))
    for value in ['do_mgL', 'do_min_mgL']:
        table[value] = table[value].where(table.eligible)
    # A listed device event ends one session and starts another.
    events = pd.to_datetime(policy['event_days'][pond]).sort_values()
    table['session'] = np.searchsorted(events.to_numpy(), table.hour.to_numpy(), side='right')
    return table


def linked_ponds(policy):
    """Ponds sharing records or possibly a device stay on the development side."""
    return {pond for group in policy['lineage_groups'] for pond in group['ponds']}


def assign_roles(hours, policy):
    """Choose held-out ponds by salted hash among unlinked ponds with test-period coverage."""
    rules = policy['partition']
    test = hours[hours.eligible & hours.hour.ge(rules['calibration_until']) & hours.hour.lt(rules['test_until'])]
    daily = test.groupby(['pond_id', test.hour.dt.normalize()]).size()
    days = daily[daily.ge(rules['minimum_hours_per_test_day'])].groupby(level=0).size()
    ponds = sorted(hours.pond_id.unique())
    linked = linked_ponds(policy)
    ranked = sorted([p for p in ponds if p not in linked and days.get(p, 0) >= rules['minimum_test_days']],
                    key=lambda p: hashlib.sha256((rules['salt'] + p).encode()).hexdigest())
    if len(ranked) < rules['test_ponds'] + rules['calibration_ponds']:
        raise ValueError('Too few eligible ponds for the declared held-out groups')
    roles = {p: 'development' for p in ponds}
    roles.update({p: 'test' for p in ranked[:rules['test_ponds']]})
    roles.update({p: 'calibration' for p in ranked[rules['test_ponds']:][:rules['calibration_ponds']]})
    return roles


def block_of(hours, policy):
    rules = policy['partition']
    edges = pd.to_datetime([rules[k] for k in ['fit_until', 'validation_until', 'calibration_until', 'test_until']])
    names = np.array(['fit', 'validation', 'calibration', 'test', 'outside'])
    return names[np.searchsorted(edges.to_numpy(), pd.DatetimeIndex(hours).to_numpy(), side='right')]


def partition_of(role, block):
    """Name the use of one pond role in one time block. None means unused."""
    if role == 'development':
        return {'fit': 'fit', 'validation': 'validation_seen_pond', 'test': 'test_seen_pond'}.get(block)
    if role == 'calibration':
        return {'fit': 'validation_unseen_pond', 'validation': 'calibration', 'calibration': 'calibration'}.get(block)
    return {'test': 'test_unseen_pond'}.get(block, 'test_unseen_pond_concurrent' if block != 'outside' else None)


def build_windows(hours, roles, policy):
    """List every supported issue hour and horizon. Both issue and target share one block."""
    rules = policy['windows']
    rows = []
    for (pond, session), group in hours.groupby(['pond_id', 'session'], sort=True):
        eligible = set(group.hour[group.eligible])
        for hour in sorted(eligible):
            history = [hour - HOUR * k for k in range(rules['history_hours'])]
            present = [h in eligible for h in history]
            if sum(present) < rules['minimum_history_hours'] or not all(present[:rules['required_recent_hours']]):
                continue
            for horizon in rules['horizons_hours']:
                target = hour + HOUR * horizon
                if target not in eligible:
                    continue
                blocks = block_of([hour, target], policy)
                if blocks[0] != blocks[1]:
                    continue
                partition = partition_of(roles[pond], blocks[0])
                if partition:
                    rows.append((pond, session, hour, horizon, target, partition))
    columns = ['pond_id', 'session', 'issue_hour', 'horizon_hours', 'target_hour', 'partition']
    return pd.DataFrame(rows, columns=columns)


def verify_source(source, policy):
    acquisition = json.loads((source / 'acquisition.json').read_text(encoding='utf-8'))
    if acquisition['commit'] != policy['source']['commit']:
        raise ValueError('Source commit differs from the policy')
    for item in acquisition['files']:
        path = (source / item['relative_path']).resolve()
        if not path.is_relative_to(source.resolve()) or digest(path) != item['sha256']:
            raise ValueError('Source file differs from the pinned acquisition: ' + item['relative_path'])
    return {item['relative_path']: item['sha256'] for item in acquisition['files']}


def residual_sharing(hours):
    """Count identical hourly DO/pH/temperature vectors left between ponds after exclusions."""
    rows = hours[hours.eligible].dropna(subset=['ph', 'temperature_c'])
    vectors = rows.groupby(['hour', 'do_mgL', 'ph', 'temperature_c']).pond_id.nunique()
    return int(vectors.gt(1).sum())


def build(source, policy_path):
    policy = json.loads(Path(policy_path).read_text(encoding='utf-8'))
    inputs = verify_source(source, policy)
    files = sorted((source / 'csv').glob('ara2_*.csv'))
    if {f.stem for f in files} != set(policy['event_days']):
        raise ValueError('Policy ponds differ from the source tables')
    hours = pd.concat([hourly(read_pond(f), f.stem, policy) for f in files], ignore_index=True)
    if residual_sharing(hours):
        raise ValueError('Identical hourly records remain between ponds')
    roles = assign_roles(hours, policy)
    return policy, inputs, hours, roles, build_windows(hours, roles, policy)


def run(source, policy_path, output):
    if output.exists():
        raise FileExistsError('Use a new release directory: ' + str(output))
    policy, inputs, hours, roles, windows = build(source, policy_path)
    output.mkdir(parents=True)
    hours.to_csv(output / 'hours.csv', index=False, lineterminator='\n', float_format='%.10g')
    windows.to_csv(output / 'windows.csv', index=False, lineterminator='\n')
    (output / 'policy.json').write_bytes(Path(policy_path).read_bytes())
    counts = windows.groupby(['partition', 'horizon_hours']).agg(windows=('pond_id', 'size'), ponds=('pond_id', 'nunique'))
    manifest = {'version': policy['version'], 'species': policy['species'], 'source': policy['source'],
                'source_sha256': inputs, 'preparation_sha256': digest(Path(__file__)), 'roles': roles,
                'eligible_hours': {p: int(g.eligible.sum()) for p, g in hours.groupby('pond_id')},
                'counts': [{'partition': p, 'horizon_hours': int(h), **{k: int(v) for k, v in row.items()}}
                           for (p, h), row in counts.iterrows()],
                'files_sha256': {name: digest(output / name) for name in ['hours.csv', 'windows.csv', 'policy.json']}}
    (output / 'manifest.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('Datasets/external/fwi_campaign_2026'))
    parser.add_argument('--policy', type=Path, default=Path('docs/data/fwi-policy.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = run(args.source, args.policy, args.output)
    print(json.dumps({k: manifest[k] for k in ['roles', 'eligible_hours', 'counts', 'files_sha256']}, indent=1))


if __name__ == '__main__':
    main()
