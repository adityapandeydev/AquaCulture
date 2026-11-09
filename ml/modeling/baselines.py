"""Non-parametric forecasts using only explicitly admitted historical references."""
import numpy as np
import pandas as pd


def predict_references(observations, index, model):
    if model not in {'persistence', 'daily_seasonal_persistence'}:
        raise ValueError('Unknown baseline')
    if observations.observation_id.isna().any() or observations.observation_id.duplicated().any():
        raise ValueError('Unique observation identities required')
    if index.window_id.isna().any() or index.window_id.duplicated().any():
        raise ValueError('Unique expected window IDs required')
    lookup = observations.set_index('observation_id')
    rows = []
    for window in index.to_dict('records'):
        row = {key: window[key] for key in ['window_id', 'session_id', 'partition', 'horizon_hours', 'issue_time',
                                           'target_observation_id', 'configuration'] if key in window}
        row.update({'model': model, 'point_mgL': None, 'status': 'unavailable', 'reason': 'seasonal_reference_unavailable'})
        seasonal = model == 'daily_seasonal_persistence'
        if seasonal and window['seasonal_matched'] != True:
            rows.append(row)
            continue
        reference_id = window['seasonal_reference_id'] if seasonal else window['persistence_reference_id']
        if pd.isna(reference_id) or reference_id not in lookup.index:
            raise ValueError('Admitted baseline reference is missing')
        reference = lookup.loc[reference_id]
        issue = pd.Timestamp(window['issue_time'])
        actual_time = pd.Timestamp(reference.available_at)
        expected_time = issue + pd.Timedelta(hours=window['horizon_hours'] - 24) if seasonal else issue
        if (actual_time > issue or actual_time != expected_time or reference.session_id != window['session_id']
                or reference.partition != window['partition']):
            raise ValueError('Baseline reference violates issue-time, seasonal phase or partition/session boundary')
        value = float(reference.do_mgL)
        if (not np.isfinite(value) or value < 0 or reference.do_mgL_eligible != True
                or reference.preparation_imputed != False):
            raise ValueError('Admitted baseline reference is not a valid prepared measurement')
        row.update({'point_mgL': value, 'status': 'ok', 'reason': None})
        rows.append(row)
    return pd.DataFrame(rows)
