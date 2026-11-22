"""Load the selected artifacts and combine their quantile forecasts."""
import json
import pickle
from pathlib import Path

import numpy as np

from ml.data.files import digest

from .network import load_network, predict, tensors


class Network:
    """Equal mean of the registered seeds of one network family."""

    def __init__(self, paths):
        self.members = [load_network(p) for p in paths]

    def predict(self, samples):
        return np.mean([predict(m, *tensors(samples, mean, scale, 'cpu')[:2]) for m, mean, scale in self.members], axis=0)


def selected_artifacts(simple, neural):
    """Paths and recorded hashes of each family's selected artifacts."""
    simple, neural = Path(simple), Path(neural)
    first, second = (json.loads((p / 'run.json').read_text(encoding='utf-8')) for p in (simple, neural))
    result = {f: {(simple / first[f]['artifact']).as_posix(): first[f]['artifact_sha256']} for f in ('ridge', 'trees')}
    for family in ('gru', 'tcn'):
        result[family] = {(neural / p).as_posix(): h for p, h in second['families'][family]['artifacts'].items()}
    return result


def load_families(artifacts):
    """Check every hash before reading any artifact."""
    for files in artifacts.values():
        for path, expected in files.items():
            if digest(path) != expected:
                raise ValueError('Artifact differs from its record: ' + path)
    models = {f: pickle.loads(Path(next(iter(artifacts[f]))).read_bytes()) for f in ('ridge', 'trees')}
    models.update({f: Network(list(artifacts[f])) for f in ('gru', 'tcn')})
    return models


def blend(forecasts, weights):
    if abs(sum(weights.values()) - 1) > 1e-12:
        raise ValueError('Blend weights must sum to one')
    return sum(weights[f] * forecasts[f] for f in weights)
