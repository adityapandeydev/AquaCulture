"""Matched physical-unit metrics with explicit missing-prediction denominators."""
import numpy as np
import pandas as pd


def lower_do_threshold(training_observations):
    frame = training_observations
    if (frame.empty or frame.partition.isna().any() or not frame.partition.eq('train').all()
            or frame.observation_id.isna().any() or frame.observation_id.duplicated().any()):
        raise ValueError('Use distinct training observations only for the lower-DO threshold')
    values = pd.to_numeric(frame.do_mgL, errors='coerce').to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('Invalid training DO measurements')
    return float(np.quantile(values, .1, method='linear'))


def _join(expected, predictions):
    for frame in [expected, predictions]:
        if frame.window_id.isna().any() or frame.window_id.duplicated().any():
            raise ValueError('Unique nonmissing window IDs required')
    if not set(predictions.window_id) <= set(expected.window_id):
        raise ValueError('Prediction references an unexpected window')
    if not predictions.status.isin(['ok', 'unavailable', 'failed']).all():
        raise ValueError('Unknown prediction status')
    truth = pd.to_numeric(expected.observed_do_mgL, errors='coerce').to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(truth).all() or (truth < 0).any():
        raise ValueError('Expected targets must be finite prepared DO measurements')
    context = [key for key in ['session_id', 'partition', 'configuration', 'horizon_hours', 'issue_time', 'target_observation_id']
               if key in predictions and key in expected]
    joined = expected.merge(predictions[['window_id', 'point_mgL', 'status'] + context], on='window_id',
                            how='left', validate='one_to_one', suffixes=('', '_predicted'), indicator=True)
    returned = joined['_merge'].eq('both')
    for key in context:
        if not joined.loc[returned, key].astype(str).eq(joined.loc[returned, key + '_predicted'].astype(str)).all():
            raise ValueError('Prediction context differs from expected windows: ' + key)
    point = pd.to_numeric(joined.point_mgL, errors='coerce').to_numpy(dtype=float, na_value=np.nan)
    valid = returned.to_numpy(dtype=bool) & joined.status.eq('ok').fillna(False).to_numpy(dtype=bool) & np.isfinite(point) & (point >= 0)
    return joined, point, valid


def score_predictions(expected, predictions, persistence=None):
    joined, point, valid = _join(expected, predictions)
    n, count = len(expected), int(valid.sum())
    ok = joined.status.eq('ok').fillna(False).to_numpy(dtype=bool)
    result = {'expected_windows': n, 'valid_predictions': count,
              'missing_predictions': int(joined['_merge'].eq('left_only').sum()),
              'unavailable_predictions': int(joined.status.eq('unavailable').sum()),
              'failed_predictions': int(joined.status.eq('failed').sum()),
              'invalid_predictions': int((ok & ~valid).sum()),
              'prediction_coverage': count / n if n else None, 'complete_predictions': n > 0 and count == n,
              'mae_mgL': None, 'rmse_mgL': None, 'mean_signed_bias_mgL': None,
              'mae_skill_vs_persistence': None, 'skill_status': 'not_requested'}
    truth = pd.to_numeric(joined.observed_do_mgL).to_numpy(dtype=float)
    if count:
        errors = point[valid] - truth[valid]
        result.update({'mae_mgL': float(np.mean(np.abs(errors))), 'rmse_mgL': float(np.sqrt(np.mean(errors ** 2))),
                       'mean_signed_bias_mgL': float(np.mean(errors))})
    if persistence is not None:
        _, reference, ref_valid = _join(expected, persistence)
        if not result['complete_predictions']:
            result['skill_status'] = 'requires_complete_paired_predictions'
        elif not ref_valid.all():
            result['skill_status'] = 'reference_incomplete'
        else:
            baseline_mae = float(np.mean(np.abs(reference - truth)))
            if baseline_mae == 0:
                result['skill_status'] = 'baseline_zero_error'
            else:
                result['mae_skill_vs_persistence'] = 1 - result['mae_mgL'] / baseline_mae
                result['skill_status'] = 'computed_on_complete_cohort'
    return result
