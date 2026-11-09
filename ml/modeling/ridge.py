"""Closed-form lag regression with training-fitted scaling and data-only artifacts."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _matrix(x, shape=None, require_rows=True):
    array = np.asarray(x, dtype=np.float64)
    if (array.ndim != 3 or min(array.shape[1:]) < 1 or (require_rows and len(array) == 0)
            or (shape is not None and tuple(array.shape[1:]) != tuple(shape)) or not np.isfinite(array).all()):
        raise ValueError('Finite [examples, history, features] arrays with the fitted shape are required')
    return array.reshape(len(array), array.shape[1] * array.shape[2])


@dataclass(frozen=True)
class RidgeForecaster:
    alpha: float
    input_shape: tuple
    mean: np.ndarray
    scale: np.ndarray
    coefficients: np.ndarray
    intercept: float

    def __post_init__(self):
        if len(self.input_shape) != 2 or any(type(n) is not int or n < 1 for n in self.input_shape):
            raise ValueError('Invalid fitted input shape')
        width = self.input_shape[0] * self.input_shape[1]
        if any(a.shape != (width,) or not np.isfinite(a).all() for a in [self.mean, self.scale, self.coefficients]):
            raise ValueError('Invalid fitted vectors')
        if (self.scale <= 0).any() or not np.isfinite(self.alpha) or self.alpha <= 0 or not np.isfinite(self.intercept):
            raise ValueError('Invalid regularization, scale or intercept')

    def predict(self, x):
        features = _matrix(x, self.input_shape, require_rows=False)
        predicted = ((features - self.mean) / self.scale) @ self.coefficients + self.intercept
        if not np.isfinite(predicted).all():
            raise ValueError('Ridge produced non-finite outputs')
        return predicted

    def to_dict(self):
        return {'version': 'ridge-lag-v1', 'alpha': float(self.alpha), 'input_shape': list(self.input_shape),
                'mean': self.mean.tolist(), 'scale': self.scale.tolist(), 'coefficients': self.coefficients.tolist(),
                'intercept': float(self.intercept), 'standard_deviation_ddof': 0, 'dtype': 'float64'}

    def save(self, path):
        with Path(path).open('x', encoding='utf-8') as stream:
            json.dump(self.to_dict(), stream, indent=2, allow_nan=False)

    @classmethod
    def load(cls, path):
        try:
            record = json.loads(Path(path).read_text(encoding='utf-8'))
            if record['version'] != 'ridge-lag-v1' or record['dtype'] != 'float64' or record['standard_deviation_ddof'] != 0:
                raise ValueError('Unknown ridge artifact version or preprocessing')
            return cls(float(record['alpha']), tuple(record['input_shape']),
                       *[np.asarray(record[key], dtype=np.float64) for key in ['mean', 'scale', 'coefficients']],
                       float(record['intercept']))
        except (KeyError, TypeError) as error:
            raise ValueError('Malformed ridge artifact') from error


def fit_ridge(x, y, alpha):
    features = _matrix(x)
    target = np.asarray(y, dtype=np.float64)
    if target.shape != (len(features),) or not np.isfinite(target).all() or not np.isfinite(alpha) or alpha <= 0:
        raise ValueError('Finite aligned scalar targets and positive finite alpha are required')
    mean = features.mean(axis=0)
    spread = features.std(axis=0, ddof=0)
    constant = np.ptp(features, axis=0) == 0
    mean = np.where(constant, features[0], mean)
    scale = np.where(~constant & (spread > 0), spread, 1.)
    standardized = (features - mean) / scale
    intercept = float(target.mean())
    coefficients = np.linalg.solve(standardized.T @ standardized + float(alpha) * np.eye(features.shape[1]),
                                   standardized.T @ (target - intercept))
    return RidgeForecaster(float(alpha), tuple(int(n) for n in np.asarray(x).shape[1:]), mean, scale, coefficients, intercept)
