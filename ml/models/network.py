"""Compact GRU and TCN quantile forecasters, trained from scratch."""
import numpy as np
import torch
from torch import nn

from ml.data.arrays import CHANNELS, HISTORY, HORIZONS, fill_history

INPUTS = 2 * len(CHANNELS) + 3


def inputs(samples, mean, scale):
    """Standardized channels, presence flags, DO relative to the latest value, and the clock."""
    filled, present = fill_history(samples.x)
    values = np.where(np.isfinite(filled), (filled - mean) / scale, 0.)
    relative = values[:, :, :1] - values[:, -1:, :1]
    hours = (samples.hour[:, None] - np.arange(HISTORY - 1, -1, -1)[None]) % 24
    angle = 2 * np.pi * hours / 24
    time = np.stack([np.sin(angle), np.cos(angle)], axis=2)
    return np.concatenate([values, present, relative, time], axis=2).astype(np.float32)


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
