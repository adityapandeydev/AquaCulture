"""Seed aggregation that never substitutes the best replica for the primary artifact."""
import numpy as np


def summarize_replicas(replicas, seeds=(17, 29, 43)):
    if [row['seed'] for row in replicas] != list(seeds):
        raise ValueError('All registered seeds must be reported once, in registered order')
    complete = all(row['status'] == 'ok' and row['validation']['complete_predictions'] for row in replicas)
    fields = ['mae_mgL', 'rmse_mgL', 'mean_signed_bias_mgL', 'mae_skill_vs_persistence']
    mean, ranges = {'complete_predictions': complete}, {}
    for field in fields:
        values = [row.get('validation', {}).get(field) for row in replicas]
        if any(v is None or not np.isfinite(v) for v in values):
            mean[field], ranges[field] = None, None
        else:
            mean[field] = float(np.mean(np.abs(values) if field == 'mean_signed_bias_mgL' else values))
            ranges[field] = [float(min(values)), float(max(values))]
    return {'complete': complete, 'mean': mean, 'range': ranges,
            'bias_aggregation': 'mean_absolute_per_seed_bias', 'primary_seed': 17}


def choose_setting(trials):
    eligible = [row for row in trials if row['summary']['complete']
                and row['summary']['mean']['mae_mgL'] is not None
                and np.isfinite(row['summary']['mean']['mae_mgL'])]
    return min(eligible, key=lambda row: (row['summary']['mean']['mae_mgL'], row['parameter_count'], row['trial_index'])) if eligible else None
