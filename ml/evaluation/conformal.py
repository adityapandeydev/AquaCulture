"""Conformal adjustment of symmetric quantile pairs."""
import numpy as np


def fit_offsets(y, forecast, quantiles, pairs):
    """Finite-sample offset per horizon and pair from calibration targets [n, h]."""
    quantiles = list(quantiles)
    offsets = []
    for j in range(y.shape[1]):
        keep = np.isfinite(y[:, j])
        row = []
        for low, high in pairs:
            a, b = forecast[keep, j, quantiles.index(low)], forecast[keep, j, quantiles.index(high)]
            score = np.sort(np.maximum(a - y[keep, j], y[keep, j] - b))
            rank = int(np.ceil((len(score) + 1) * (high - low)))
            if rank > len(score):
                raise ValueError('Too few calibration targets for the requested coverage')
            row.append(float(score[rank - 1]))
        offsets.append(row)
    return offsets


def apply_offsets(forecast, quantiles, pairs, offsets):
    """Move each pair outward or inward, keeping the median and the order."""
    quantiles, result = list(quantiles), forecast.copy()
    for j, row in enumerate(offsets):
        for (low, high), offset in zip(pairs, row):
            result[:, j, quantiles.index(low)] -= offset
            result[:, j, quantiles.index(high)] += offset
    middle = quantiles.index(0.5)
    for i in range(middle - 1, -1, -1):
        result[:, :, i] = np.minimum(result[:, :, i], result[:, :, i + 1])
    for i in range(middle + 1, len(quantiles)):
        result[:, :, i] = np.maximum(result[:, :, i], result[:, :, i - 1])
    return np.maximum(result, 0)
