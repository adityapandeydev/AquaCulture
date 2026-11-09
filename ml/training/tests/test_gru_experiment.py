import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from ml.data.eligibility import digest
from ml.data.evaluation_plan import build_plan
from ml.data.windows import build_windows
from ml.training.data import materialize_development
from ml.training.gru import run_gru, train_case


class GRUExperimentTests(unittest.TestCase):
    def fixture(self, root):
        observations = pd.DataFrame({'observation_id': [str(i) for i in range(110)], 'session_id': 'fixture',
            'partition': ['train'] * 100 + ['validation'] * 10,
            'available_at': pd.date_range('2026-01-01 01:00', periods=110, freq='h', tz='UTC'),
            'do_mgL': 7 + np.sin(np.arange(110) / 5) * .2, 'do_mgL_eligible': True, 'preparation_imputed': False})
        contract = {'version': 'fixture', 'history_hours': 6, 'horizons_hours': [1],
                    'input_configurations': {'do_only': ['do_mgL']}, 'target': {'column': 'do_mgL'}}
        windows = build_windows(observations, contract)
        index = build_plan(observations, windows, contract, 24)
        descriptor = root / 'docs/data/prepared-release.json'
        descriptor.parent.mkdir(parents=True)
        descriptor.write_text('{}')
        frozen = root / 'release'
        (frozen / 'policies').mkdir(parents=True)
        for name in ['release-criteria.json', 'evaluation-policy.json']:
            (frozen / 'policies' / name).write_bytes((Path('docs/data') / name).read_bytes())
        config_path, settings_path = root / 'config.json', root / 'settings.json'
        config_path.write_bytes(Path('ml/training/configs/do_pilot.json').read_bytes())
        settings_path.write_bytes(Path('ml/training/configs/gru_settings.json').read_bytes())
        fake = SimpleNamespace(root=frozen, descriptor_path=descriptor, contract=contract,
            development=lambda p, c, h, dtype: materialize_development(observations, windows, contract, p, c, h, dtype),
            baseline_context=lambda p, c, h: (observations[observations.partition.eq(p)].copy(), index[index.partition.eq(p)].reset_index(drop=True)),
            training_observations=lambda: observations[observations.partition.eq('train')].copy())
        return fake, config_path, settings_path

    def test_dry_run_never_initializes_torch_or_fits_and_cuda_failure_leaves_no_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake, config, settings = self.fixture(root)
            with patch('ml.training.gru.PreparedRelease', return_value=fake), patch('ml.training.gru.capture_provenance', return_value={}), \
                    patch('ml.training.gru.prepare_randomness') as prepare, patch('ml.training.gru.check_device') as device, \
                    patch('ml.training.gru.fit_replica') as fit, contextlib.redirect_stdout(io.StringIO()):
                result = run_gru(config, settings, root / 'dry', repository=root, dry_run=True)
                self.assertFalse(result['training_performed'])
                prepare.assert_not_called()
                device.assert_not_called()
                fit.assert_not_called()
                device.side_effect = RuntimeError('CUDA unavailable')
                with self.assertRaises(RuntimeError):
                    run_gru(config, settings, root / 'failed', repository=root)
                self.assertFalse((root / 'failed').exists())

    def test_failed_replicas_cannot_select_a_setting_or_substitute_a_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake, _, settings_path = self.fixture(root)
            batches = {p: fake.development(p, 'do_only', 1, np.float64) for p in ['train', 'validation']}
            contexts = {p: fake.baseline_context(p, 'do_only', 1) for p in batches}
            settings = json.loads(settings_path.read_text())
            criteria = json.loads(Path('docs/data/release-criteria.json').read_text())
            policy = json.loads(Path('docs/data/evaluation-policy.json').read_text())
            with patch('ml.training.gru.fit_replica', side_effect=ValueError('numerical failure')) as fit:
                record, forecasts = train_case(batches, contexts, settings, criteria, policy, root / 'case', lambda _: None)
            self.assertEqual(fit.call_count, 12)
            self.assertIsNone(record['selected'])
            self.assertIsNone(forecasts)
            self.assertTrue(all(not trial['summary']['complete'] for trial in record['trials']))
            self.assertFalse((root / 'case/selected_seed_17.pt').exists())

    @unittest.skipUnless(importlib.util.find_spec('torch'), 'Requires the separate model environment')
    def test_full_synthetic_runner_records_three_seeds_and_loadable_primary(self):
        from ml.training.gru_fit import fit_replica
        from ml.modeling.gru import load_checkpoint
        def short_cpu_fit(train, val, setting, settings, seed, device, output, seconds, cap, emit):
            self.assertEqual(device, 'cuda:0')
            return fit_replica(train, val, setting, {**settings, 'maximum_epochs': 2}, seed, 'cpu', output, seconds, cap, emit)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake, config, settings = self.fixture(root)
            with patch('ml.training.gru.PreparedRelease', return_value=fake), patch('ml.training.gru.capture_provenance', return_value={'synthetic_fixture': True}), \
                    patch('ml.training.gru.prepare_randomness'), patch('ml.training.gru.check_device', return_value={'synthetic_test': True}), \
                    patch('ml.training.gru.fit_replica', side_effect=short_cpu_fit), contextlib.redirect_stdout(io.StringIO()):
                result = run_gru(config, settings, root / 'run', repository=root)
            self.assertEqual(result['status'], 'development_gru_completed')
            case = result['cases'][0]
            self.assertFalse(case['model_qualified'])
            self.assertEqual(len(case['trials']), 4)
            self.assertEqual([r['seed'] for r in case['selected']['replicas']], [17, 29, 43])
            _, record = load_checkpoint(root / 'run/do_only/horizon_1/selected_seed_17.pt')
            self.assertEqual(record['seed'], 17)
            frame = pd.read_csv(root / 'run/predictions.csv')
            self.assertEqual(set(frame.seed), {17, 29, 43})
            self.assertEqual(set(frame.partition), {'train', 'validation'})
            for name, expected in result['outputs_sha256'].items():
                self.assertEqual(digest(root / 'run' / name), expected)
            with self.assertRaises(FileExistsError):
                run_gru(config, settings, root / 'run', repository=root)


if __name__ == '__main__':
    unittest.main()
