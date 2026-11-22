"""Naive point forecasts used as references."""
import numpy as np

from .history import HISTORY, HORIZONS


def persistence(samples):
    return np.repeat(samples.last[:, None], len(HORIZONS), axis=1)


def yesterday(samples):
    """Value 24 hours before each target, or the latest value when that hour is missing."""
    columns = [samples.x[:, HISTORY - 1 + h - 24, 0] for h in HORIZONS]
    values = np.stack(columns, axis=1)
    return np.where(np.isfinite(values), values, samples.last[:, None])


def fit_profile(samples):
    """Average DO by hour of day, giving every fitting pond equal weight."""
    ponds = []
    for pond in np.unique(samples.pond):
        mask = samples.pond == pond
        ponds.append([samples.last[mask & (samples.hour == h)].mean() if (mask & (samples.hour == h)).any() else np.nan
                      for h in range(24)])
    profile = np.nanmean(np.array(ponds), axis=0)
    if not np.isfinite(profile).all():
        raise ValueError('Every hour of day needs fitting data')
    return profile


def profile(samples, values):
    columns = [samples.last + values[(samples.hour + h) % 24] - values[samples.hour] for h in HORIZONS]
    return np.maximum(np.stack(columns, axis=1), 0)


def naive_forecasts(samples, values):
    return {'persistence': persistence(samples), 'yesterday': yesterday(samples), 'profile': profile(samples, values)}
