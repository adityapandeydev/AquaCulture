"""Inspect the pinned FWI campaign snapshot without modifying measurements."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .eligibility import digest


def inspect_pond(frame):
    required = ['Date/Time (IST)', 'DO (mg/L)', 'pH', 'Temperature (\u00b0C)',
                'QC_Flag_DateTime', 'QC_Flag_DO', 'QC_Flag_pH']
    if list(frame.columns) != required:
        raise ValueError('Unexpected FWI pond schema')
    timestamps = pd.to_datetime(frame[required[0]], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    utc = timestamps.dt.tz_localize('Asia/Kolkata').dt.tz_convert('UTC')
    values = frame[required[1:4]].apply(pd.to_numeric, errors='coerce')
    steps = timestamps.diff().dt.total_seconds()
    ordered = timestamps.dropna().sort_values()
    gaps = ordered.diff().dt.total_seconds()
    do = values['DO (mg/L)']
    numeric_do = np.isfinite(do) & do.gt(0)
    clear_do = numeric_do & frame.QC_Flag_DO.fillna('').eq('')
    # Structural capacity only. Four distinct exact quarter-hour timestamps per hour,
    # positive finite DO and no exported DO flag. No threshold is inferred from outcomes.
    support = pd.DataFrame({'time': timestamps, 'usable': clear_do})
    support['hour'] = timestamps.dt.floor('h')
    support['quarter'] = timestamps.dt.minute
    support['aligned'] = timestamps.dt.minute.isin([0, 15, 30, 45]) & timestamps.dt.second.eq(0)
    hours = support.groupby('hour').agg(rows=('time', 'size'), unique=('time', 'nunique'),
                                        usable=('usable', 'all'), aligned=('aligned', 'all'))
    admitted = hours.index[(hours.rows == 4) & (hours.unique == 4) & hours.usable & hours.aligned]
    admitted_set = set(admitted)
    counts = {}
    for horizon in [1, 3]:
        counts[str(horizon)] = sum(all(hour + pd.Timedelta(hours=offset) in admitted_set
                                       for offset in range(-5, horizon + 1)) for hour in admitted)
    summary = {'rows': len(frame), 'invalid_timestamps': int(timestamps.isna().sum()),
        'first_local': str(timestamps.min()), 'last_local': str(timestamps.max()),
        'first_utc': str(utc.min()), 'last_utc': str(utc.max()),
        'span_days': float((timestamps.max() - timestamps.min()).total_seconds() / 86400),
        'duplicate_timestamps': int(timestamps.duplicated(keep=False).sum()),
        'source_order_backsteps': int(steps.lt(0).sum()), 'source_order_exact_15min_steps': int(steps.eq(900).sum()),
        'sorted_gaps_over_20min': int(gaps.gt(1200).sum()),
        'maximum_sorted_gap_hours': float(gaps.max() / 3600),
        'zero_counts': {column: int(values[column].eq(0).sum()) for column in values},
        'negative_counts': {column: int(values[column].lt(0).sum()) for column in values},
        'nonfinite_counts': {column: int((~np.isfinite(values[column])).sum()) for column in values},
        'positive_finite_do_rows': int(numeric_do.sum()), 'positive_finite_unflagged_do_rows': int(clear_do.sum()),
        'do_range_mgL': [float(do.min()), float(do.max())],
        'flag_counts': {column: frame[column].dropna().value_counts().to_dict() for column in required[4:]},
        'structural_complete_hour_count': len(admitted), 'structural_six_hour_windows_by_horizon': counts}
    return summary, timestamps, values


def run(source, output):
    if output.exists():
        raise FileExistsError('Use a fresh FWI audit directory')
    acquisition_path = source / 'acquisition.json'
    acquisition = json.loads(acquisition_path.read_text(encoding='utf-8'))
    inputs = {str(acquisition_path): digest(acquisition_path)}
    for item in acquisition['files']:
        path = (source / item['relative_path']).resolve()
        if not path.is_relative_to(source.resolve()):
            raise ValueError('Acquisition path escapes the source directory')
        if digest(path) != item['sha256']:
            raise ValueError('Acquisition hash mismatch: ' + str(path))
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != item['git_blob_sha1']:
            raise ValueError('Pinned Git blob mismatch')
        inputs[str(path)] = item['sha256']
    files = sorted((source / 'csv').glob('ara2_*.csv'))
    if len(files) != 17:
        raise ValueError('Expected 17 pinned pond tables')
    workbook = pd.ExcelFile(source / 'Data Campaign Data.xlsx', engine='openpyxl')
    summaries, signatures = [], {}
    for path in files:
        frame = pd.read_csv(path)
        summary, timestamps, values = inspect_pond(frame)
        excel = workbook.parse(path.stem)
        time_equal = len(excel) == len(frame) and timestamps.reset_index(drop=True).equals(pd.to_datetime(excel.iloc[:, 0]).reset_index(drop=True))
        values_equal = len(excel) == len(frame) and np.allclose(values.to_numpy(), excel.iloc[:, 1:4].to_numpy(dtype=float),
                                                              rtol=0, atol=1e-10, equal_nan=True)
        if not time_equal or not values_equal:
            raise ValueError('CSV/workbook measurement mismatch: ' + path.stem)
        summary.update({'pond_id': path.stem, 'csv_workbook_measurements_match': True})
        summaries.append(summary)
        rows = pd.concat([timestamps.rename('time'), values], axis=1).dropna()
        signatures[path.stem] = set(map(tuple, rows.itertuples(index=False, name=None)))
        print(path.stem, summary['rows'], 'rows;', summary['structural_complete_hour_count'], 'structurally complete hours', flush=True)
    shared = []
    for index, left in enumerate(signatures):
        for right in list(signatures)[index + 1:]:
            common = signatures[left] & signatures[right]
            if common:
                times = sorted({row[0] for row in common})
                longest = current = 1
                for previous, following in zip(times, times[1:]):
                    current = current + 1 if following - previous == pd.Timedelta(minutes=15) else 1
                    longest = max(longest, current)
                shared.append({'pond_a': left, 'pond_b': right, 'identical_time_and_three_channel_rows': len(common),
                               'longest_shared_exact_15min_run_rows': longest})
    comparison = pd.read_csv(source / 'csv/Continuous_Monitor_vs_ProDSS_Comparison.csv', header=None, skiprows=2)
    paired = comparison[[3, 4]].apply(pd.to_numeric, errors='coerce').dropna()
    differences = (paired[4] - paired[3]).abs()
    comparison_summary = {'pairs': len(paired), 'mean_absolute_difference_mgL': float(differences.mean()),
                          'median_absolute_difference_mgL': float(differences.median()),
                          'maximum_absolute_difference_mgL': float(differences.max()),
                          'interpretation': 'Publisher-listed spot pairs, some approximate times. No fitted calibration or forecast error estimate.'}
    for name, expected in inputs.items():
        if digest(Path(name)) != expected:
            raise ValueError('Source changed during audit')
    output.mkdir(parents=True)
    pd.DataFrame(summaries).drop(columns=['zero_counts', 'negative_counts', 'nonfinite_counts', 'flag_counts',
                                        'structural_six_hour_windows_by_horizon']).to_csv(output / 'pond_summary.csv', index=False)
    record = {'version': 'fwi-discovery-audit-v1', 'repository_commit': acquisition['commit'],
        'inputs_sha256': inputs, 'audit_source_sha256': digest(Path(__file__)),
        'timezone': 'Asia/Kolkata (CSV explicitly labels IST; publisher places collection in Andhra Pradesh)',
        'training_approved': False, 'measurement_changes': False, 'species_per_pond': 'unresolved',
        'ponds': summaries, 'shared_time_and_water_vectors': shared, 'spot_do_comparison': comparison_summary,
        'total_rows': sum(row['rows'] for row in summaries),
        'structural_hourly_support_definition': 'Exactly four distinct on-grid quarter-hour rows with positive finite DO and no exported DO flag. Six adjacent supported hours and full future path. Diagnostic capacity before event/session decisions, lineage resolution and partitioning.',
        'source_specific_zero_rule': 'Publisher explicitly identifies exact zero DO/pH/temperature as equipment artifacts. Raw bytes preserved.',
        'approval_blockers': ['Harvest/reinstallation/device-move sessions unresolved', 'Per-pond species and farm independence unresolved',
            'Formal reuse/license scope requires recording beyond a named CC identifier',
            'Source-specific aggregation and quality policy required for 15-minute cadence',
            'Drift/cleaning, calibration and spot-reference discrepancies require review',
            'QC flag generation/availability and overwritten conditional-format flags require review'],
        'outputs_sha256': {'pond_summary.csv': digest(output / 'pond_summary.csv')}}
    (output / 'audit.json').write_text(json.dumps(record, indent=2, allow_nan=False), encoding='utf-8')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('Datasets/external/fwi_campaign_2026'))
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.source, arguments.output)
