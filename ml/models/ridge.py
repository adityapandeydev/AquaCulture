"""Ridge regression on the change from the latest value, with fitted residual quantiles."""
import numpy as np

from ml.data.arrays import HORIZONS

from .features import clock, tabular


class Ridge:
    def __init__(self, alpha, quantiles):
        self.alpha, self.quantiles = alpha, np.asarray(quantiles)

    def _design(self, samples):
        base = tabular(samples)
        base = np.where(np.isfinite(base), (base - self.mean) / self.scale, 0.)
        # The daily cycle depends on the oxygen level, so clock terms also scale the latest value.
        time = clock(samples.hour)
        return np.concatenate([base, time * base[:, [0]], np.ones((len(samples), 1))], axis=1)

    def fit(self, samples):
        raw = tabular(samples)
        self.mean, self.scale = np.nanmean(raw, axis=0), np.nanstd(raw, axis=0)
        self.scale[self.scale == 0] = 1
        design = self._design(samples)
        self.weights, self.residuals = [], []
        for j in range(len(HORIZONS)):
            rows = np.isfinite(samples.y[:, j])
            a, b = design[rows], (samples.y[:, j] - samples.last)[rows]
            penalty = self.alpha * np.eye(a.shape[1])
            penalty[-1, -1] = 0
            weights = np.linalg.solve(a.T @ a + penalty, a.T @ b)
            self.weights.append(weights)
            # Fitted residual quantiles, separately for each six-hour part of the day.
            part, error = samples.hour[rows] // 6, b - a @ weights
            self.residuals.append(np.stack([np.quantile(error[part == p], self.quantiles) for p in range(4)]))
        return self

    def predict(self, samples):
        design = self._design(samples)
        output = []
        for j in range(len(HORIZONS)):
            center = samples.last + design @ self.weights[j]
            output.append(center[:, None] + self.residuals[j][samples.hour // 6])
        return np.maximum(np.stack(output, axis=1), 0)
