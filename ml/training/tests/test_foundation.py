import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd

from ml.training.data import PreparedRelease, materialize_development
from ml.training.runtime import check_device
from ml.training.experiment import validate_config


class FoundationTests(unittest.TestCase):
    def fixture(self):
        obs = pd.DataFrame({'observation_id': [str(i) for i in range(10)], 'session_id': 'a', 'partition': 'train',
                             'available_at': pd.date_range('2026-01-01 01:00', periods=10, freq='h', tz='UTC'),
                             'do_mgL': np.arange(10, dtype=float), 'do_mgL_eligible': True})
        contract = {'version': 'fixture', 'history_hours': 6, 'horizons_hours': [1], 'input_configurations': {'do_only': ['do_mgL']}}
        contract['target'] = {'column': 'do_mgL'}
        from ml.data.windows import build_windows
        return obs, contract, build_windows(obs, contract)

    def test_shapes_feature_order_and_independent_arrays(self):
        obs, contract, windows = self.fixture()
        batch = materialize_development(obs, windows, contract, 'train', 'do_only', 1)
        self.assertEqual(batch.x.shape, (4, 6, 1))
        self.assertEqual(batch.y.shape, (4,))
        self.assertEqual(batch.x.dtype, np.float32)
        np.testing.assert_array_equal(batch.x[0, :, 0], np.arange(6))
        np.testing.assert_array_equal(batch.y, [6, 7, 8, 9])
        batch.x[0, 0, 0] = 999
        self.assertEqual(obs.iloc[0].do_mgL, 0)

    def test_calibration_and_test_access_are_locked(self):
        obs, contract, windows = self.fixture()
        for partition in ['calibration', 'test']:
            held_out = obs.assign(partition=partition)
            held_out_windows = [{**window, 'partition': partition} for window in windows]
            with self.assertRaises(ValueError):
                materialize_development(held_out, held_out_windows, contract, partition, 'do_only', 1)

    def test_cross_partition_references_cannot_supply_training_labels(self):
        obs, contract, windows = self.fixture()
        obs.loc[6, 'partition'] = 'test'
        with self.assertRaises(ValueError):
            materialize_development(obs, windows, contract, 'train', 'do_only', 1)

    def test_unknown_config_and_seed_are_rejected(self):
        config = {'version': 'do-experiment-foundation-v1', 'release_descriptor': 'docs/data/prepared-release.json',
                  'configuration': 'do_only', 'horizon_hours': 1, 'seed': 17, 'neural_device': 'cuda'}
        validate_config(config)
        for key, value in [('seed', 999), ('configuration', 'nitrogen'), ('horizon_hours', 6), ('neural_device', 'auto')]:
            changed = {**config, key: value}
            with self.assertRaises(ValueError):
                validate_config(changed)

    def test_gpu_request_never_silently_falls_back(self):
        fake = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        with patch('ml.training.runtime.importlib.import_module', return_value=fake):
            with self.assertRaises(RuntimeError):
                check_device('cuda')

    def test_missing_torch_has_actionable_error(self):
        with patch('ml.training.runtime.importlib.import_module', side_effect=ModuleNotFoundError('torch')):
            with self.assertRaisesRegex(RuntimeError, 'requirements-gpu-windows'):
                check_device('cuda')

    def test_changed_release_manifest_is_rejected_before_data_access(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'release_manifest.json').write_text('changed bytes', encoding='utf-8')
            descriptor = root / 'descriptor.json'
            descriptor.write_text(json.dumps({'training_approved': True, 'status': 'ready_for_scoped_model_development',
                                  'local_release': '.', 'candidate_manifest_sha256': '0' * 64}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'checksum anchor'):
                PreparedRelease(descriptor, root)

    def test_existing_output_is_never_overwritten(self):
        from ml.training.experiment import inspect_experiment
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                inspect_experiment(Path(directory) / 'missing-config.json', Path(directory))

    def test_unknown_device_is_rejected_without_loading_torch(self):
        with patch('ml.training.runtime.importlib.import_module') as imported:
            with self.assertRaises(ValueError):
                check_device('auto')
            imported.assert_not_called()

    def test_cuda_preflight_allocates_on_cuda_and_synchronizes(self):
        tensor = MagicMock()
        tensor.__matmul__.return_value.sum.return_value.item.return_value = 8.
        fake = SimpleNamespace(__version__='fixture', version=SimpleNamespace(cuda='12.6'),
                               ones=Mock(return_value=tensor), cuda=SimpleNamespace(
                                   is_available=lambda: True, synchronize=Mock(),
                                   get_device_properties=lambda _: SimpleNamespace(name='fixture GPU', total_memory=4096 * 1024 ** 2)))
        with patch('ml.training.runtime.importlib.import_module', return_value=fake):
            report = check_device('cuda')
        self.assertEqual(report['selected_device'], 'cuda:0')
        self.assertEqual(report['total_memory_mib'], 4096)
        fake.ones.assert_called_once_with((2, 2), device='cuda:0')
        fake.cuda.synchronize.assert_called_once()

    def test_cuda_execution_failure_stops_before_training(self):
        fake = SimpleNamespace(ones=Mock(side_effect=RuntimeError('CUDA allocation failure')),
                               cuda=SimpleNamespace(is_available=lambda: True))
        with patch('ml.training.runtime.importlib.import_module', return_value=fake):
            with self.assertRaisesRegex(RuntimeError, 'no training started'):
                check_device('cuda')
        fake.ones.assert_called_once()


if __name__ == '__main__':
    unittest.main()
