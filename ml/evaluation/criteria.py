"""Development error gates, separate from model and production qualification."""
import numpy as np


def validation_error_gates(metrics, persistence, limits, minimum_skill):
    reasons = []
    if not metrics['complete_predictions']:
        reasons.append('incomplete_prediction_coverage')
    for field, cap in [('mae_mgL', limits['maximum_mae_mgL']), ('rmse_mgL', limits['maximum_rmse_mgL']),
                       ('mean_signed_bias_mgL', limits['maximum_absolute_bias_mgL'])]:
        value = metrics[field]
        if value is None or not np.isfinite(value) or abs(value) > cap:
            reasons.append(field + '_limit')
    skill = metrics['mae_skill_vs_persistence']
    if skill is None or not np.isfinite(skill) or skill < minimum_skill:
        reasons.append('insufficient_mae_improvement')
    if (metrics['rmse_mgL'] is None or persistence['rmse_mgL'] is None
            or metrics['rmse_mgL'] > persistence['rmse_mgL']):
        reasons.append('rmse_regression_or_unavailable')
    return {'passed': not reasons, 'reasons': reasons, 'model_qualified': False,
            'resource_gates': 'not_assessed', 'final_test': 'locked'}
