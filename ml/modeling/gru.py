"""Compact, newly initialized GRU with a persistence residual and fitted input buffers."""
import numpy as np
import torch
from torch import nn


class DOForecaster(nn.Module):
    def __init__(self, features, hidden_size, mean, scale):
        super().__init__()
        mean, scale = np.asarray(mean, dtype=np.float32), np.asarray(scale, dtype=np.float32)
        if (features not in {1, 3} or hidden_size not in {8, 16} or mean.shape != (features,)
                or scale.shape != (features,) or not np.isfinite(mean).all()
                or not np.isfinite(scale).all() or (scale <= 0).any()):
            raise ValueError('Invalid GRU dimensions or fitted scaling')
        self.register_buffer('mean', torch.from_numpy(mean.copy()))
        self.register_buffer('scale', torch.from_numpy(scale.copy()))
        self.gru = nn.GRU(features, hidden_size, num_layers=1, batch_first=True)
        self.head = nn.Linear(hidden_size, 1)
        # New zero residual starts at persistence; the recurrent weights are newly randomized.
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def forward(self, x):
        if x.ndim != 3 or x.shape[1] != 6 or x.shape[2] != self.mean.numel():
            raise ValueError('Expected [examples, 6, fitted feature count]')
        _, hidden = self.gru((x - self.mean) / self.scale)
        return x[:, -1, 0] + self.head(hidden[-1]).squeeze(-1) * self.scale[0]


def fit_channel_scaling(training_x):
    values = np.asarray(training_x, dtype=np.float64)
    if values.ndim != 3 or len(values) == 0 or not np.isfinite(values).all():
        raise ValueError('Finite training histories are required')
    rows = values.reshape(-1, values.shape[-1])
    mean, scale = rows.mean(axis=0), rows.std(axis=0, ddof=0)
    constant = np.ptp(rows, axis=0) == 0
    return np.where(constant, rows[0], mean).astype(np.float32), np.where(constant | (scale == 0), 1., scale).astype(np.float32)


def load_checkpoint(path, device='cpu'):
    record = torch.load(path, map_location='cpu', weights_only=True)
    if record['version'] != 'compact-do-gru-v1' or record['history_hours'] != 6:
        raise ValueError('Unknown GRU checkpoint contract')
    state = record['state_dict']
    model = DOForecaster(record['features'], record['hidden_size'], state['mean'].numpy(), state['scale'].numpy())
    if any(not torch.isfinite(value).all() for value in state.values()):
        raise ValueError('Non-finite checkpoint tensors')
    model.load_state_dict(state, strict=True)
    return model.to(device).eval(), record
