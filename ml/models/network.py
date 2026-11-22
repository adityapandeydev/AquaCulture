"""Compact GRU and TCN quantile forecasters, trained from scratch."""
import numpy as np
import torch
from torch import nn

from .features import INPUTS, inputs
from .history import HORIZONS

class CausalBlock(nn.Module):
    def __init__(self, width, dilation, dropout):
        super().__init__()
        self.pad = 2 * dilation
        self.conv = nn.Conv1d(width, width, 3, dilation=dilation)
        self.norm, self.drop = nn.GroupNorm(1, width), nn.Dropout(dropout)

    def forward(self, x):
        return x + self.drop(torch.relu(self.norm(self.conv(nn.functional.pad(x, (self.pad, 0))))))


class QuantileNetwork(nn.Module):
    def __init__(self, kind, width, quantiles, scale, dropout=0.1):
        super().__init__()
        self.kind, self.count = kind, len(quantiles)
        self.middle = list(quantiles).index(0.5)
        self.register_buffer('scale', torch.tensor(float(scale)))
        if kind == 'gru':
            self.body = nn.GRU(INPUTS, width, batch_first=True)
        elif kind == 'tcn':
            self.body = nn.Sequential(nn.Conv1d(INPUTS, width, 1), *[CausalBlock(width, d, dropout) for d in (1, 2, 4, 4)])
        else:
            raise ValueError('Unknown network kind')
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(width + INPUTS, width), nn.ReLU(),
                                  nn.Linear(width, len(HORIZONS) * self.count))
        nn.init.zeros_(self.head[-1].weight)
        nn.init.zeros_(self.head[-1].bias)

    def forward(self, x, last):
        if self.kind == 'gru':
            state = self.body(x)[1][-1]
        else:
            state = self.body(x.transpose(1, 2))[:, :, -1]
        raw = self.head(torch.cat([state, x[:, -1]], dim=1)).view(-1, len(HORIZONS), self.count)
        m = self.middle
        steps = nn.functional.softplus(raw)
        # Quantiles step outward from the median, so they cannot cross.
        below = -torch.flip(torch.cumsum(torch.flip(steps[:, :, :m], [2]), 2), [2])
        above = torch.cumsum(steps[:, :, m + 1:], 2)
        center = raw[:, :, m:m + 1]
        change = torch.cat([center + below, center, center + above], dim=2) * self.scale
        return last[:, None, None] + change


def pinball(forecast, target, quantiles, scale):
    """Mean quantile loss over available targets, in units of the DO spread."""
    present = torch.isfinite(target)
    error = torch.where(present, target, torch.zeros_like(target))[:, :, None] - forecast
    loss = torch.maximum(quantiles * error, (quantiles - 1) * error).mean(dim=2)
    return (loss * present).sum() / present.sum() / scale


def tensors(samples, mean, scale, device):
    return (torch.as_tensor(inputs(samples, mean, scale), device=device),
            torch.as_tensor(samples.last, dtype=torch.float32, device=device),
            torch.as_tensor(samples.y, dtype=torch.float32, device=device))


def predict(model, x, last):
    model.eval()
    with torch.inference_mode():
        return model(x, last).clamp_min(0).cpu().numpy().astype(float)


def load_network(path, device='cpu'):
    record = torch.load(path, map_location='cpu', weights_only=True)
    model = QuantileNetwork(record['kind'], record['width'], record['quantiles'], record['scale'][0])
    model.load_state_dict(record['state'], strict=True)
    return model.to(device).eval(), np.array(record['mean']), np.array(record['scale'])
