"""Pond-averaged forecast metrics in physical units."""
import numpy as np

from ml.data.arrays import HORIZONS


def by_pond(values, pond):
    return {p: float(values[pond == p].mean()) for p in np.unique(pond)}


def macro(values, pond):
    """Average within ponds first, so ponds with more windows do not dominate."""
    return float(np.mean(list(by_pond(values, pond).values())))


def point_metrics(samples, forecast):
    """MAE, RMSE, bias and per-pond MAE for each horizon of an [n, 4] forecast."""
    rows = []
    for j, horizon in enumerate(HORIZONS):
        keep = np.isfinite(samples.y[:, j])
        error, pond = forecast[keep, j] - samples.y[keep, j], samples.pond[keep]
        valid = np.isfinite(error)
        if not valid.all():
            raise ValueError('Every expected window needs a finite forecast')
        rows.append({'horizon': horizon, 'windows': int(keep.sum()), 'mae': macro(np.abs(error), pond),
                     'rmse': float(np.sqrt(macro(error ** 2, pond))), 'bias': macro(error, pond),
                     'pond_mae': by_pond(np.abs(error), pond)})
    return rows


def quantile_metrics(samples, forecast, quantiles, nominal=0.9):
    """Pinball loss, interval coverage, width and interval score for an [n, 4, q] forecast."""
    quantiles = np.asarray(quantiles)
    low = int(np.argmin(np.abs(quantiles - (1 - nominal) / 2)))
    high = int(np.argmin(np.abs(quantiles - (1 + nominal) / 2)))
    rows = []
    for j, horizon in enumerate(HORIZONS):
        keep = np.isfinite(samples.y[:, j])
        y, f, pond = samples.y[keep, j], forecast[keep, j], samples.pond[keep]
        error = y[:, None] - f
        loss = np.maximum(quantiles * error, (quantiles - 1) * error).mean(axis=1)
        a, b = f[:, low], f[:, high]
        inside = ((y >= a) & (y <= b)).astype(float)
        score = (b - a) + 2 / (1 - nominal) * (np.maximum(a - y, 0) + np.maximum(y - b, 0))
        rows.append({'horizon': horizon, 'pinball': macro(loss, pond), 'coverage': macro(inside, pond),
                     'pond_coverage': by_pond(inside, pond), 'width': macro(b - a, pond),
                     'interval_score': macro(score, pond)})
    return rows


def probability_below(forecast, quantiles, threshold):
    """Probability of a value under the threshold, interpolated between forecast quantiles."""
    quantiles = np.asarray(quantiles)
    n, horizons, _ = forecast.shape
    result = np.empty((n, horizons))
    for i in range(n):
        for j in range(horizons):
            q = forecast[i, j]
            if threshold <= q[0]:
                result[i, j] = quantiles[0] / 2
            elif threshold > q[-1]:
                result[i, j] = 1 - (1 - quantiles[-1]) / 2
            else:
                result[i, j] = np.interp(threshold, q + np.arange(len(q)) * 1e-9, quantiles)
    return result


def alert_metrics(samples, forecast, quantiles, threshold, hourly_rate, onset=False):
    """Brier skill against the fitting-set event frequency of the target hour.

    With onset, only windows whose latest hour is at or above the threshold count.
    """
    probability = probability_below(forecast, quantiles, threshold)
    rows = []
    for j, horizon in enumerate(HORIZONS):
        keep = np.isfinite(samples.y[:, j])
        if onset:
            keep &= samples.last >= threshold
        event, pond = (samples.y[keep, j] < threshold).astype(float), samples.pond[keep]
        reference = hourly_rate[(samples.hour[keep] + horizon) % 24]
        brier, base = macro((probability[keep, j] - event) ** 2, pond), macro((reference - event) ** 2, pond)
        warned = probability[keep, j] >= 0.5
        hits = float((warned & (event == 1)).sum())
        rows.append({'horizon': horizon, 'threshold': threshold, 'events': int(event.sum()), 'brier': brier,
                     'brier_reference': base, 'brier_skill': 1 - brier / base if base > 0 else None,
                     'recall': hits / event.sum() if event.sum() else None,
                     'precision': hits / warned.sum() if warned.sum() else None})
    return rows


def event_rate(samples, threshold):
    """Fitting-set frequency of low DO by hour of day."""
    low = samples.last < threshold
    return np.array([low[samples.hour == h].mean() for h in range(24)])


def relative_score(forecast_mae, naive_maes):
    """Mean ratio to the strongest naive forecast over sets and horizons. Lower is better."""
    ratios = [forecast_mae[s][j] / min(m[j] for m in naive_maes[s].values())
              for s in forecast_mae for j in range(len(HORIZONS))]
    return float(np.mean(ratios))


def gain_interval(samples, forecast, reference, resamples=2000, seed=17):
    """Percentile interval of the MAE gain, resampling whole pond-days within each pond."""
    rng, rows = np.random.default_rng(seed), []
    day = samples.issue.astype('datetime64[D]')
    for j in range(len(HORIZONS)):
        keep = np.isfinite(samples.y[:, j])
        errors = np.abs(np.stack([forecast[keep, j], reference[keep, j]]) - samples.y[keep, j])
        pond, date = samples.pond[keep], day[keep]
        tables = []
        for p in np.unique(pond):
            blocks = [(pond == p) & (date == d) for d in np.unique(date[pond == p])]
            tables.append(np.array([[*errors[:, b].sum(axis=1), b.sum()] for b in blocks]))
        gains = []
        for _ in range(resamples):
            totals = [t[rng.integers(0, len(t), len(t))].sum(axis=0) for t in tables]
            model, base = np.mean([t[:2] / t[2] for t in totals], axis=0)
            gains.append(1 - model / base)
        rows.append([float(v) for v in np.quantile(gains, [0.025, 0.975])])
    return rows
