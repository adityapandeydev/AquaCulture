"""Model input definition shared by training and serving. Depends on NumPy only."""
from dataclasses import dataclass

import numpy as np

CHANNELS = ('do_mgL', 'ph', 'temperature_c')
HISTORY = 24
HORIZONS = (1, 3, 6, 12)


@dataclass(frozen=True)
class Samples:
    """Histories [n, 24, 3] with gaps as NaN, oldest first, and targets [n, 4] with gaps as NaN.

    `hour` is the local clock hour in which the latest hourly value starts.
    """
    x: np.ndarray
    y: np.ndarray
    hour: np.ndarray
    pond: np.ndarray
    issue: np.ndarray

    def __len__(self):
        return len(self.hour)

    @property
    def last(self):
        return self.x[:, -1, 0]


def fill_history(x):
    """Carry gaps forward inside each history, then fill leading gaps from its first value.

    Returns filled values and a presence mask. A channel missing for a whole history stays NaN.
    """
    present = np.isfinite(x)
    n, steps, channels = x.shape
    position = np.where(present, np.arange(steps)[None, :, None], -1)
    forward = np.maximum.accumulate(position, axis=1)
    first = np.where(present.any(axis=1), present.argmax(axis=1), 0)
    source = np.where(forward >= 0, forward, first[:, None, :])
    return np.take_along_axis(x, source, axis=1), present
