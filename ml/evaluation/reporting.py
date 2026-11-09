"""Shared development reports for baseline and learned forecasts on matched windows."""
import numpy as np
import pandas as pd

from .metrics import score_predictions


def validate_development_case(index):
    if index.empty or not index.partition.isin(['train', 'validation']).all() or index.partition.nunique() != 1:
        raise ValueError('Only one nonempty development partition may be scored')
    for column in ['configuration', 'horizon_hours', 'session_id']:
        if index[column].isna().any() or index[column].nunique() != 1:
            raise ValueError('Score each session/configuration/horizon separately')


def prediction_frame(index, values, model):
    values = np.asarray(values, dtype=np.float64)
    if values.shape != (len(index),):
        raise ValueError('One scalar forecast per expected window is required')
    columns = ['window_id', 'session_id', 'partition', 'configuration', 'horizon_hours', 'issue_time', 'target_observation_id']
    result = index[columns].copy()
    valid = np.isfinite(values) & (values >= 0)
    result['model'], result['point_mgL'] = model, values
    result['status'] = np.where(valid, 'ok', 'failed')
    result['reason'] = np.where(valid, None, 'nonfinite_or_negative_prediction')
    return result


def evaluate_predictions(observations, index, predictions, threshold, policy):
    validate_development_case(index)
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError('Invalid training-frozen lower-DO threshold')
    expected = index.copy()
    truth = observations.set_index('observation_id').do_mgL
    expected['observed_do_mgL'] = expected.target_observation_id.map(truth)
    all_rows, metrics = [], []
    context = {column: index[column].iloc[0] for column in ['partition', 'configuration', 'horizon_hours', 'session_id']}
    context['horizon_hours'] = int(context['horizon_hours'])
    for model, prediction in predictions.items():
        details = prediction.merge(expected[['window_id', 'observed_do_mgL'] + policy['comparison_cohorts']],
                                   on='window_id', validate='one_to_one')
        details['point_mgL'] = pd.to_numeric(details.point_mgL, errors='coerce').to_numpy(dtype=float, na_value=np.nan)
        details['error_mgL'] = (details.point_mgL - details.observed_do_mgL).where(details.status.eq('ok'))
        details['absolute_error_mgL'] = details.error_mgL.abs()
        all_rows.append(details)
    for cohort in policy['comparison_cohorts']:
        selected = expected[expected[cohort].eq(True)]
        subsets = {'all_targets': selected, 'training_lower_decile': selected[selected.observed_do_mgL.le(threshold)]}
        for subset, rows in subsets.items():
            reference = predictions['persistence'][predictions['persistence'].window_id.isin(rows.window_id)]
            for model, prediction in predictions.items():
                scored = prediction[prediction.window_id.isin(rows.window_id)]
                result = score_predictions(rows, scored, reference)
                metrics.append({**context, 'model': model, 'cohort': cohort, 'subset': subset, 'seed': None,
                                'primary_rankable': cohort == 'all_horizon_specific' and subset == 'all_targets'
                                    and result['complete_predictions'], **result})
    return pd.concat(all_rows, ignore_index=True), metrics
