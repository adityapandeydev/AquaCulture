"""Measure pre-split forecasting feasibility; no model fitting or final window release."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


HISTORIES = [6, 12, 24]
HORIZONS = [1, 3, 6]


def count_examples(inputs, targets, history, horizon):
    """Require consecutive historical inputs and a complete future DO observation path.

    The issue hour is the last of `history` completed bins. Targets are indexed
    by availability time, so horizon=1 refers to the next completed hour.
    These counts precede partition boundaries and are not independent samples.
    """
    if not isinstance(history, int) or not isinstance(horizon, int) or min(history, horizon) < 1:
        raise ValueError('History and horizon must be positive integer hours')
    for frame in [inputs, targets]:
        if frame.duplicated(['session_id', 'available_at']).any() or frame.available_at.isna().any():
            raise ValueError('Unique nonmissing session/time keys required')
        if frame.available_at.dt.tz is None:
            raise ValueError('Timezone-aware availability times required')
    counts = {}
    for session, group in inputs.groupby('session_id'):
        valid_input = set(group.loc[group.candidate_eligible, 'available_at'])
        future = targets[targets.session_id.eq(session)]
        valid_target = set(future.loc[future.candidate_eligible, 'available_at'])
        count = 0
        for issue in valid_input:
            history_times = pd.date_range(end=issue, periods=history, freq='h')
            future_times = pd.date_range(start=issue + pd.Timedelta(hours=1), periods=horizon, freq='h')
            if set(history_times) <= valid_input and set(future_times) <= valid_target:
                count += 1
        counts[session] = count
    return counts


def valid_runs(group):
    group = group.sort_values('available_at')
    mask = group.candidate_eligible
    breaks = ~mask | ~mask.shift(fill_value=False) | group.available_at.diff().ne(pd.Timedelta(hours=1))
    return [int(len(run)) for _, run in group[mask].groupby(breaks.cumsum()[mask])]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(prepared, selection_path, output):
    if output.exists():
        raise FileExistsError(output)
    paths = [prepared / 'hourly_channels.csv.gz', prepared / 'hourly_configurations.csv',
             prepared / 'aggregation.json', selection_path]
    inputs = {str(path): digest(path) for path in paths}
    aggregation = json.loads(paths[2].read_text())
    for path, expected in aggregation['inputs_sha256'].items():
        if digest(Path(path)) != expected:
            raise ValueError('Upstream aggregation input changed: ' + path)
    if aggregation['policy']['version'] != 'oman-hourly-v1':
        raise ValueError('Unreviewed aggregation policy')
    selection = json.loads(selection_path.read_text())
    channels, configs = pd.read_csv(paths[0]), pd.read_csv(paths[1])
    for frame in [channels, configs]:
        frame['available_at'] = pd.to_datetime(frame.available_at, utc=True)
    if channels.duplicated(['session_id', 'channel', 'available_at']).any():
        raise ValueError('Duplicate hourly channel key')
    target = channels[channels.channel.eq('do')]
    counts, summaries = [], []
    for configuration, group in configs.groupby('configuration'):
        for history in HISTORIES:
            for horizon in HORIZONS:
                per_session = count_examples(group, target, history, horizon)
                for session, count in per_session.items():
                    recording = group.loc[group.session_id.eq(session), 'recording'].iloc[0]
                    role = selection['session_roles'].get(session)
                    if role is None:
                        raise ValueError('Session missing a release decision: ' + session)
                    counts.append({'session_id': session, 'recording': recording,
                                   'configuration': configuration, 'history_hours': history,
                                   'horizon_hours': horizon, 'pre_split_examples': count, 'role': role})
        for session, subset in group.groupby('session_id'):
            runs = valid_runs(subset)
            do = target[target.session_id.eq(session) & target.candidate_eligible]
            summaries.append({'session_id': session, 'configuration': configuration,
                              'recording': subset.recording.iloc[0], 'role': selection['session_roles'][session],
                              'eligible_hours': int(subset.candidate_eligible.sum()),
                              'eligible_run_lengths_hours': runs,
                              'longest_run_hours': max(runs, default=0),
                              'first_eligible_bin_end': subset.loc[subset.candidate_eligible, 'available_at'].min().isoformat() if runs else None,
                              'last_eligible_bin_end': subset.loc[subset.candidate_eligible, 'available_at'].max().isoformat() if runs else None,
                              'eligible_do_summary_min_mgL': float(do.value.min()) if len(do) else None,
                              'eligible_do_summary_max_mgL': float(do.value.max()) if len(do) else None})
    report = {'version': 'oman-release-feasibility-v1', 'training_approved': False,
              'partitioned': False, 'selection': selection, 'inputs_sha256': inputs,
              'count_rule': 'Consecutive eligible historical configuration bins including issue hour; all future DO bins through target eligible; same session; before split boundaries.',
              'sessions': summaries}
    if any(digest(Path(path)) != expected for path, expected in inputs.items()):
        raise ValueError('Input changed during feasibility review')
    output.mkdir(parents=True)
    frame = pd.DataFrame(counts)
    frame.to_csv(output / 'example_counts.csv', index=False)
    (output / 'eligibility.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(frame[frame.configuration.eq('do_only')].groupby(['role', 'history_hours', 'horizon_hours']).pre_split_examples.sum().to_string())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, default=Path('Datasets/processed/oman-aggregation-2026-11-05'))
    parser.add_argument('--selection', type=Path, default=Path('docs/data/release-selection.json'))
    parser.add_argument('--output', type=Path, default=Path('Datasets/processed/oman-eligibility-2026-11-05'))
    args = parser.parse_args()
    run(args.prepared, args.selection, args.output)
