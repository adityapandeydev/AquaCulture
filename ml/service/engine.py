"""Verified model bundle and forecast computation. Needs NumPy and ONNX Runtime only."""
import json
from pathlib import Path

import numpy as np
import onnxruntime

from ml.data.files import digest
from ml.evaluation.conformal import apply_offsets
from ml.evaluation.metrics import probability_below
from ml.models.features import inputs, tabular
from ml.models.history import HORIZONS
from ml.models.ridge import Ridge

VERSION = 'carp-bundle-v1'


class BundleError(RuntimeError):
    pass


def load_ridge(path, quantiles):
    with np.load(path) as data:
        model = Ridge(None, quantiles)
        model.mean, model.scale = data['mean'], data['scale']
        model.weights, model.residuals = list(data['weights']), list(data['residuals'])
    return model


class TreeArrays:
    """Boosted quantile trees as flat node arrays."""

    def __init__(self, path):
        with np.load(path) as data:
            self.feature, self.threshold, self.value = data['feature'], data['threshold'], data['value']
            self.left, self.right, self.missing_left = data['left'], data['right'], data['missing_left']
            self.roots, self.baseline, self.depth = data['roots'], data['baseline'], int(data['depth'])

    def predict(self, samples):
        features, last = tabular(samples), samples.last
        output = np.empty((len(samples), *self.baseline.shape))
        for i, row in enumerate(features):
            node = self.roots
            for _ in range(self.depth):
                value = row[self.feature[node]]
                go_left = np.where(np.isnan(value), self.missing_left[node], value <= self.threshold[node])
                node = np.where(go_left, self.left[node], self.right[node])
            output[i] = self.baseline + self.value[node].sum(axis=2) + last[i]
        return np.sort(np.maximum(output, 0), axis=2)


class NetworkSet:
    """Equal mean of the seeds of one network family."""

    def __init__(self, paths, scaling):
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        self.sessions = [onnxruntime.InferenceSession(str(p), options, providers=['CPUExecutionProvider']) for p in paths]
        self.mean, self.scale = (np.array(scaling[k]) for k in ('mean', 'scale'))

    def predict(self, samples):
        feed = {'x': inputs(samples, self.mean, self.scale), 'last': samples.last.astype(np.float32)}
        outputs = [np.maximum(s.run(['forecast'], feed)[0], 0).astype(float) for s in self.sessions]
        return np.mean(outputs, axis=0)


class Bundle:
    def __init__(self, folder, manifest_sha256=None):
        folder = Path(folder)
        path = folder / 'manifest.json'
        if not path.is_file():
            raise BundleError('Bundle manifest is missing')
        self.sha256 = digest(path)
        if manifest_sha256 and self.sha256 != manifest_sha256:
            raise BundleError('Bundle manifest differs from the released one')
        self.manifest = json.loads(path.read_text(encoding='utf-8'))
        if self.manifest['version'] != VERSION or tuple(self.manifest['horizons_hours']) != HORIZONS:
            raise BundleError('Unsupported bundle version')
        for name, expected in self.manifest['files_sha256'].items():
            file = (folder / name).resolve()
            if not file.is_relative_to(folder.resolve()) or not file.is_file() or digest(file) != expected:
                raise BundleError('Bundle file is missing or changed: ' + name)
        self.quantiles = list(self.manifest['quantiles'])
        self.families = {'ridge': load_ridge(folder / 'ridge.npz', self.quantiles), 'trees': TreeArrays(folder / 'trees.npz')}
        for family in ('gru', 'tcn'):
            paths = [folder / name for name in self.manifest['networks'][family]]
            self.families[family] = NetworkSet(paths, self.manifest['scaling'])

    def quantile_forecast(self, samples):
        """Calibrated quantiles [n, 4, q] of the released blend."""
        weights = self.manifest['weights']
        mixed = sum(weights[f] * self.families[f].predict(samples) for f in weights)
        result = apply_offsets(mixed, self.quantiles, self.manifest['pairs'], self.manifest['offsets'])
        if not np.isfinite(result).all():
            raise ArithmeticError('Forecast is not finite')
        return result

    def forecast(self, samples):
        """Released outputs per horizon for one history. Outputs that failed acceptance are withheld."""
        quantiles = self.quantile_forecast(samples)
        threshold = self.manifest['alert_threshold_mgL']
        probability = probability_below(quantiles, self.quantiles, threshold)[0]
        low, high = self.quantiles.index(0.05), self.quantiles.index(0.95)
        rows = []
        for j, horizon in enumerate(HORIZONS):
            released, q = self.manifest['released'][str(horizon)], quantiles[0, j]
            rows.append({'horizon_hours': horizon,
                         'point_mgL': round(float(q[self.quantiles.index(0.5)]), 3) if released['point'] else None,
                         'interval_90': {'low_mgL': round(float(q[low]), 3), 'high_mgL': round(float(q[high]), 3)}
                         if released['interval'] else None,
                         'low_oxygen': {'threshold_mgL': threshold, 'probability': round(float(probability[j]), 4)}
                         if released['alert'] else None,
                         'withheld': [name for name in ('point', 'interval', 'alert') if not released[name]]})
        return rows

    def outside_range(self, samples):
        """Channels whose values fall outside the range seen during fitting."""
        names = []
        for c, (channel, (low, high)) in enumerate(self.manifest['training_range'].items()):
            values = samples.x[0, :, c]
            values = values[np.isfinite(values)]
            if len(values) and (values.min() < low or values.max() > high):
                names.append(channel)
        return names
