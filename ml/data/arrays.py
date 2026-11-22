"""Turn the verified carp release into model arrays, keeping reserved partitions closed."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.models.history import CHANNELS, HISTORY, HORIZONS, Samples

from .files import digest

DEVELOPMENT = ('fit', 'validation_seen_pond', 'validation_unseen_pond')


def verify_release(descriptor, repository='.'):
    anchor = json.loads(Path(descriptor).read_text(encoding='utf-8'))
    root = Path(repository) / anchor['local_release']
    if digest(root / 'manifest.json') != anchor['manifest_sha256']:
        raise ValueError('Release manifest differs from its anchor')
    for name, expected in anchor['files_sha256'].items():
        if digest(root / name) != expected:
            raise ValueError('Release file differs from its anchor: ' + name)
    return anchor, root


def assemble(hours, windows):
    """Build samples for one partition from eligible hours of the window's own session."""
    eligible = hours[hours.eligible]
    grids = {}
    for key, group in eligible.groupby(['pond_id', 'session']):
        times = group.hour.to_numpy()
        index = pd.date_range(times.min(), times.max(), freq='h')
        grids[key] = (index[0], group.set_index('hour').reindex(index)[list(CHANNELS)].to_numpy(dtype=float))
    rows = windows.pivot_table(index=['pond_id', 'session', 'issue_hour'], columns='horizon_hours',
                               values='target_hour', aggfunc='first')
    rows = rows.reindex(columns=list(HORIZONS))
    n = len(rows)
    x, y = np.full((n, HISTORY, len(CHANNELS)), np.nan), np.full((n, len(HORIZONS)), np.nan)
    for i, ((pond, session, issue), targets) in enumerate(rows.iterrows()):
        start, grid = grids[pond, session]
        now = int((issue - start) / pd.Timedelta(hours=1))
        first = max(0, now - HISTORY + 1)
        x[i, HISTORY - (now - first + 1):] = grid[first:now + 1]
        for j, horizon in enumerate(HORIZONS):
            if pd.notna(targets[horizon]):
                y[i, j] = grid[now + horizon, 0]
    expected = rows.notna().to_numpy()
    if not np.array_equal(expected, np.isfinite(y)) or not np.isfinite(x[:, -3:, 0]).all():
        raise ValueError('Windows reference unsupported hours')
    issue = pd.DatetimeIndex(rows.index.get_level_values('issue_hour'))
    return Samples(x, y, issue.hour.to_numpy(), rows.index.get_level_values('pond_id').to_numpy(dtype=str),
                   issue.to_numpy())


class CarpRelease:
    """Development access by default. Reserved partitions need an explicit request."""

    def __init__(self, descriptor='docs/data/carp-release.json', repository='.'):
        self.anchor, root = verify_release(descriptor, repository)
        self._hours = pd.read_csv(root / 'hours.csv', parse_dates=['hour'])
        self._windows = pd.read_csv(root / 'windows.csv', parse_dates=['issue_hour', 'target_hour'])

    def samples(self, partition, reserved=False):
        if partition not in DEVELOPMENT and not (reserved and partition in self.anchor['reserved_partitions']):
            raise PermissionError('Partition is reserved: ' + partition)
        return assemble(self._hours, self._windows[self._windows.partition.eq(partition)])
