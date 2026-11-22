"""Features for tabular and neural models. Depends on NumPy only."""
import numpy as np

from .history import CHANNELS, HISTORY, fill_history

INPUTS = 2 * len(CHANNELS) + 3


def clock(hour):
    angle = 2 * np.pi * np.asarray(hour) / 24
    return np.stack([np.sin(angle), np.cos(angle), np.sin(2 * angle), np.cos(2 * angle)], axis=1)


def tabular(samples):
    """Latest DO, DO changes, pH and temperature context, window statistics, gaps and clock."""
    filled, present = fill_history(samples.x)
    do, last = filled[:, :, 0], samples.last[:, None]
    ph, temperature = filled[:, :, 1], filled[:, :, 2]
    recent = np.diff(do[:, -7:], axis=1)
    context = [ph[:, [-1]], ph[:, [-1]] - ph[:, [-4]], ph[:, [-1]] - ph[:, [0]],
               temperature[:, [-1]], temperature[:, [-1]] - temperature[:, [-4]], temperature[:, [-1]] - temperature[:, [0]]]
    stats = [f(do, axis=1, keepdims=True) for f in (np.mean, np.min, np.max, np.std)]
    return np.concatenate([last, do[:, :-1] - last, recent, *context, *stats,
                           present[:, :, 0].sum(axis=1, keepdims=True), clock(samples.hour)], axis=1)


def inputs(samples, mean, scale):
    """Standardized channels, presence flags, DO relative to the latest value, and the clock."""
    filled, present = fill_history(samples.x)
    values = np.where(np.isfinite(filled), (filled - mean) / scale, 0.)
    relative = values[:, :, :1] - values[:, -1:, :1]
    hours = (samples.hour[:, None] - np.arange(HISTORY - 1, -1, -1)[None]) % 24
    angle = 2 * np.pi * hours / 24
    time = np.stack([np.sin(angle), np.cos(angle)], axis=2)
    return np.concatenate([values, present, relative, time], axis=2).astype(np.float32)
