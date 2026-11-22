"""Gradient-boosted quantile trees on the change from the latest value."""
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from ml.data.arrays import HORIZONS

from .features import tabular


class Trees:
    def __init__(self, leaves, leaf_size, quantiles, iterations=250, rate=0.05, seed=17):
        self.quantiles = tuple(quantiles)
        self.settings = dict(max_leaf_nodes=leaves, min_samples_leaf=leaf_size, max_iter=iterations,
                             learning_rate=rate, l2_regularization=1.0, early_stopping=False, random_state=seed)

    def fit(self, samples, progress=None):
        features = tabular(samples)
        self.models = []
        for j, horizon in enumerate(HORIZONS):
            rows = np.isfinite(samples.y[:, j])
            change = (samples.y[:, j] - samples.last)[rows]
            self.models.append([HistGradientBoostingRegressor(loss='quantile', quantile=q, **self.settings)
                                .fit(features[rows], change) for q in self.quantiles])
            if progress:
                progress(f'  +{horizon} h fitted')
        return self

    def predict(self, samples):
        features = tabular(samples)
        output = np.stack([np.stack([m.predict(features) for m in row], axis=1) for row in self.models], axis=1)
        return np.sort(np.maximum(output + samples.last[:, None, None], 0), axis=2)
