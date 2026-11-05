"""Coverage-gated Oman hourly summaries. No filling, fitting or training approval."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .quality import CHANNELS


POLICY = {
    'version': 'oman-hourly-v1', 'bin_seconds': 3600,
    'minimum_readings_per_minute': 3, 'minimum_covered_minutes': 54,
    'maximum_gap_seconds_including_edges': 180, 'maximum_end_age_seconds': 60,
    'aggregation': 'mean_of_covered_minute_medians', 'filling': 'none',
    'review_flags': 'retain_and_report', 'training_approved': False,
}
REVIEWS = ['zero_review', 'rapid_change_review', 'exact_plateau_review']


def aggregate_channel(frame):
    """Aggregate one channel in one session; return empty bins as explicit missingness."""
    if 'session_id' in frame and frame.session_id.nunique() != 1:
        raise ValueError('Exactly one session is required')
    frame = frame.sort_values('timestamp_utc').reset_index(drop=True).copy()
    if frame.empty or frame.timestamp_utc.isna().any() or frame.timestamp_utc.duplicated().any():
        raise ValueError('Nonempty unique timestamps required')
    if frame.timestamp_utc.dt.tz is None:
        raise ValueError('Timezone-aware timestamps required')
    values = pd.to_numeric(frame.value, errors='coerce')
    valid = ~frame.invalid & values.notna() & np.isfinite(values)
    frame['value'] = values
    start = frame.timestamp_utc.min().floor('h')
    last = frame.timestamp_utc.max().floor('h')
    groups = {key: group for key, group in frame.groupby(frame.timestamp_utc.dt.floor('h'))}
    rows = []
    for left in pd.date_range(start, last, freq='h'):
        right = left + pd.Timedelta(hours=1)
        group = groups.get(left, frame.iloc[:0])
        measured = group.loc[valid.reindex(group.index)]
        minute = measured.groupby(measured.timestamp_utc.dt.floor('min')).value.agg(['count', 'median'])
        covered = minute[minute['count'].ge(POLICY['minimum_readings_per_minute'])]
        times = measured.timestamp_utc
        boundaries = pd.concat([pd.Series([left]), times.reset_index(drop=True), pd.Series([right])], ignore_index=True)
        max_gap = boundaries.diff().dt.total_seconds().max()
        age = (right - times.iloc[-1]).total_seconds() if len(times) else 3600.
        enough = len(covered) >= POLICY['minimum_covered_minutes']
        continuity = max_gap <= POLICY['maximum_gap_seconds_including_edges']
        fresh = age <= POLICY['maximum_end_age_seconds']
        eligible = enough and continuity and fresh
        mean = float(covered['median'].mean()) if len(covered) else np.nan
        reviews = {reason + '_rows': int(measured[reason].sum()) for reason in REVIEWS}
        rows.append({'bin_start': left, 'available_at': right, 'rows': len(group),
                     'valid_rows': len(measured), 'invalid_rows': len(group) - len(measured),
                     'covered_minutes': len(covered), 'maximum_gap_seconds': max_gap,
                     'end_age_seconds': age, 'measured_mean': mean,
                     'measured_min': measured.value.min(), 'measured_max': measured.value.max(),
                     'eligible': eligible, 'value': mean if eligible else np.nan,
                     'insufficient_coverage': not enough, 'gap_exceeded': not continuity,
                     'stale_at_bin_end': not fresh,
                     'review_free_eligible': eligible and not any(reviews.values()), **reviews})
    return pd.DataFrame(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, sessions, quality, output):
    if output.exists():
        raise FileExistsError(output)
    inventory = json.loads((sessions / 'inventory.json').read_text())
    flags_path = quality / 'row_quality_flags.csv.gz'
    flags = pd.read_csv(flags_path)
    flags['timestamp_utc'] = pd.to_datetime(flags.timestamp_utc, utc=True)
    inputs = {str(flags_path): sha256(flags_path), str(sessions / 'inventory.json'): sha256(sessions / 'inventory.json')}
    all_bins = []
    for recording, filename in [('offline', 'raw_readings.csv'), ('live', 'raw_readings_new.csv')]:
        path = root / 'data/raw' / recording / filename
        inputs[str(path)] = sha256(path)
        if inputs[str(path)] != inventory['recordings'][recording]['source_sha256']:
            raise ValueError('Raw source does not match session inventory')
        raw = pd.read_csv(path)
        raw['source_row'] = np.arange(2, len(raw) + 2)
        sidecar = sessions / f'{recording}_timestamp_rows.csv.gz'
        inputs[str(sidecar)] = sha256(sidecar)
        mapped = pd.read_csv(sidecar)
        mapped['timestamp_utc'] = pd.to_datetime(mapped.timestamp_utc, utc=True)
        keys = ['session_id', 'source_row', 'timestamp_utc', 'model_use']
        joined = mapped[keys].merge(flags, on=keys, how='left', validate='one_to_one', indicator=True)
        if not joined['_merge'].eq('both').all():
            raise ValueError('Missing or inconsistent quality flags')
        joined = joined.merge(raw[['source_row'] + list(CHANNELS.values())], on='source_row', validate='one_to_one')
        for session, group in joined.groupby('session_id'):
            for parameter, column in CHANNELS.items():
                frame = group[['timestamp_utc', 'session_id', column] + [parameter + '_' + reason for reason in ['invalid'] + REVIEWS]].copy()
                frame.columns = ['timestamp_utc', 'session_id', 'value', 'invalid'] + REVIEWS
                bins = aggregate_channel(frame.reset_index(drop=True))
                bins['session_id'], bins['recording'], bins['channel'] = session, recording, parameter
                bins['model_use'] = group.model_use.iloc[0]
                bins['session_candidate'] = not group.model_use.iloc[0].startswith('excluded')
                bins['candidate_eligible'] = bins.eligible & bins.session_candidate
                all_bins.append(bins)
    result = pd.concat(all_bins, ignore_index=True)
    if len(flags) != sum(v['mapped_rows'] for v in inventory['recordings'].values()):
        raise ValueError('Quality row accounting mismatch')
    configs = []
    for name, channels in [('do_only', ['do']), ('do_temperature_ph', list(CHANNELS))]:
        for (session, time), group in result[result.channel.isin(channels)].groupby(['session_id', 'available_at']):
            if set(group.channel) != set(channels) or len(group) != len(channels):
                raise ValueError('Incomplete or duplicate configuration channels')
            configs.append({'configuration': name, 'session_id': session, 'available_at': time,
                            'recording': group.recording.iloc[0],
                            'candidate_eligible': bool(group.candidate_eligible.all()),
                            'review_free_eligible': bool(group.candidate_eligible.all() and group.review_free_eligible.all())})
    configurations = pd.DataFrame(configs)
    summary = {'policy': POLICY, 'inputs_sha256': inputs, 'training_approved': False,
               'channel_counts': result.groupby(['recording', 'channel'])[['eligible', 'candidate_eligible', 'review_free_eligible']].sum().reset_index().to_dict('records'),
               'configuration_counts': configurations.groupby(['recording', 'configuration'])[['candidate_eligible', 'review_free_eligible']].sum().reset_index().to_dict('records'),
               'coverage_sensitivity': []}
    for threshold in [48, 54, 57]:
        mask = result.session_candidate & result.covered_minutes.ge(threshold) & ~result.gap_exceeded & ~result.stale_at_bin_end
        for (recording, channel), group in result.assign(sensitivity_eligible=mask).groupby(['recording', 'channel']):
            summary['coverage_sensitivity'].append({'minimum_minutes': threshold, 'recording': recording,
                                                   'channel': channel, 'eligible_bins': int(group.sensitivity_eligible.sum())})
    if any(sha256(Path(path)) != digest for path, digest in inputs.items()):
        raise ValueError('Inputs changed during aggregation')
    output.mkdir(parents=True)
    result.to_csv(output / 'hourly_channels.csv.gz', index=False)
    configurations.to_csv(output / 'hourly_configurations.csv', index=False)
    (output / 'aggregation.json').write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary['configuration_counts'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('Datasets/external/oman_tilapia'))
    parser.add_argument('--sessions', type=Path, default=Path('Datasets/processed/oman-sessions-2026-11-05-v2'))
    parser.add_argument('--quality', type=Path, default=Path('Datasets/processed/oman-quality-2026-11-05'))
    parser.add_argument('--output', type=Path, default=Path('Datasets/processed/oman-aggregation-2026-11-05'))
    args = parser.parse_args()
    run(args.root, args.sessions, args.quality, args.output)
