"""Resolve the anchored release into development-only arrays in physical units."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.eligibility import digest
from ml.data.release import verify_release
from ml.data.windows import input_matrix


@dataclass(frozen=True)
class DevelopmentBatch:
    x: np.ndarray
    y: np.ndarray
    window_ids: tuple
    issue_times: tuple
    target_times: tuple
    features: tuple

    def summary(self):
        return {'examples': len(self.window_ids), 'x_shape': list(self.x.shape), 'y_shape': list(self.y.shape),
                'features': list(self.features), 'dtype': str(self.x.dtype)}


def materialize_development(observations, windows, contract, partition, configuration, horizon, dtype=np.float32):
    if partition not in {'train', 'validation'}:
        raise ValueError('Calibration and final-test access is locked during experiment development')
    if configuration not in contract['input_configurations'] or horizon not in contract['horizons_hours']:
        raise ValueError('Unsupported feature configuration or horizon')
    if np.dtype(dtype) not in [np.dtype('float32'), np.dtype('float64')]:
        raise ValueError('Use float32 or float64 development arrays')
    selected = sorted([w for w in windows if w['partition'] == partition and w['configuration'] == configuration
                       and w['horizon_hours'] == horizon], key=lambda w: (w['session_id'], w['issue_time']))
    if not selected:
        raise ValueError('No eligible development windows')
    if len({w['window_id'] for w in selected}) != len(selected):
        raise ValueError('Duplicate development window')
    indexed = observations.set_index('observation_id')
    x = np.stack([input_matrix(observations, w, contract) for w in selected]).astype(dtype)
    y = np.array([indexed.loc[w['target_observation_id'], contract['target']['column']]
                  for w in selected], dtype=dtype)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('Non-finite development arrays')
    return DevelopmentBatch(x, y, tuple(w['window_id'] for w in selected), tuple(w['issue_time'] for w in selected),
                            tuple(w['target_available_at'] for w in selected), tuple(contract['input_configurations'][configuration]))


class PreparedRelease:
    """Workflow guard for development access, not a filesystem security boundary."""

    def __init__(self, descriptor, repository, release_root=None):
        self.descriptor_path = Path(descriptor)
        self.anchor = json.loads(self.descriptor_path.read_text(encoding='utf-8'))
        if not self.anchor['training_approved'] or self.anchor['status'] != 'ready_for_scoped_model_development':
            raise ValueError('Prepared release is not approved for scoped model development')
        self.root = Path(release_root) if release_root else Path(repository) / self.anchor['local_release']
        self.manifest_sha256 = digest(self.root / 'release_manifest.json')
        if self.manifest_sha256 != self.anchor['candidate_manifest_sha256']:
            raise ValueError('Release manifest does not match the published checksum anchor')
        manifest = verify_release(self.root)
        if manifest['scientific_content_sha256'] != self.anchor['scientific_content_sha256']:
            raise ValueError('Scientific content differs from approved release')
        supervised = self.root / 'stages/supervised'
        self.contract = json.loads((self.root / 'policies/supervised-contract.json').read_text(encoding='utf-8'))
        self._observations = pd.read_csv(supervised / 'observations.csv.gz')
        self._observations['available_at'] = pd.to_datetime(self._observations.available_at, utc=True)
        self._windows = [json.loads(line) for line in (supervised / 'windows.jsonl').read_text(encoding='utf-8').splitlines()]
        self._counts = pd.read_csv(self.root / 'stages/partitions/split_counts.csv')
        self._evaluation = pd.read_csv(self.root / 'stages/evaluation/evaluation_index.csv')

    def development(self, partition, configuration, horizon, dtype=np.float32):
        batch = materialize_development(self._observations, self._windows, self.contract, partition, configuration, horizon, dtype=dtype)
        expected = self._counts[self._counts.partition.eq(partition) & self._counts.configuration.eq(configuration)
                                & self._counts.horizon_hours.eq(horizon)]
        if len(expected) != 1 or int(expected.examples.iloc[0]) != len(batch.window_ids):
            raise ValueError('Materialized counts differ from frozen partition manifest')
        return batch

    def baseline_context(self, partition, configuration, horizon):
        """Return only the admitted period, including older in-period seasonal references."""
        batch = self.development(partition, configuration, horizon)
        index = self._evaluation[self._evaluation.partition.eq(partition)
                                 & self._evaluation.configuration.eq(configuration)
                                 & self._evaluation.horizon_hours.eq(horizon)].copy()
        if set(index.window_id) != set(batch.window_ids) or len(index) != len(batch.window_ids):
            raise ValueError('Baseline index differs from development windows')
        observations = self._observations[self._observations.partition.eq(partition)].copy()
        return observations, index.sort_values(['session_id', 'issue_time']).reset_index(drop=True)

    def training_observations(self):
        """Distinct original training bins for training-only diagnostic statistics."""
        return self._observations[self._observations.partition.eq('train')].copy()
