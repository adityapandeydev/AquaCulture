"""CPU inference adapters for the point-forecast resource benchmark."""
from datetime import datetime, timedelta, timezone

import numpy as np


def assemble_history(rows, features):
    """Validate six already-prepared hourly bins; raw-sensor aggregation is upstream."""
    if features not in [('do_mgL',), ('do_mgL', 'temperature_c', 'ph')] or len(rows) != 6:
        raise ValueError('Use six hourly bins and the registered feature order')
    times = [datetime.fromisoformat(row['available_at'].replace('Z', '+00:00')) for row in rows]
    if any(t.tzinfo is None or t.utcoffset() is None for t in times):
        raise ValueError('Hourly availability timestamps must have a timezone')
    times = [t.astimezone(timezone.utc) for t in times]
    if any(b - a != timedelta(hours=1) for a, b in zip(times, times[1:])):
        raise ValueError('Histories must be ordered consecutive hourly bins')
    values = np.array([[row[f] for f in features] for row in rows], dtype=np.float64)
    if not np.isfinite(values).all() or (values[:, 0] < 0).any():
        raise ValueError('Finite measured features and nonnegative DO are required')
    return values[None, :, :]


class CPUForecast:
    def __init__(self, family, artifact, features):
        self.family, self.features = family, tuple(features)
        self.parameters = 0
        if family == 'persistence':
            self.model = None
        elif family == 'ridge':
            from .ridge import RidgeForecaster
            self.model = RidgeForecaster.load(artifact)
            if self.model.input_shape != (6, len(features)):
                raise ValueError('Ridge artifact feature shape differs from benchmark inputs')
            self.parameters = self.model.coefficients.size + 1
        elif family == 'gru':
            import torch
            from .gru import load_checkpoint
            torch.set_num_threads(1)
            if torch.get_num_interop_threads() != 1:
                torch.set_num_interop_threads(1)
            self.model, record = load_checkpoint(artifact, device='cpu')
            if record['features'] != len(features) or record['seed'] != 17:
                raise ValueError('Benchmark the bound feature shape and primary seed 17')
            self.parameters = sum(p.numel() for p in self.model.parameters())
        else:
            raise ValueError('Unknown CPU benchmark family')

    def prepare(self, values):
        if self.family == 'gru':
            import torch
            return torch.as_tensor(values, dtype=torch.float32, device='cpu')
        return np.asarray(values, dtype=np.float64)

    def predict(self, prepared):
        if self.family == 'persistence':
            return prepared[:, -1, 0].copy()
        if self.family == 'ridge':
            return self.model.predict(prepared)
        import torch
        with torch.inference_mode():
            return self.model(prepared).numpy()

    def from_history(self, rows):
        return self.predict(self.prepare(assemble_history(rows, self.features)))
