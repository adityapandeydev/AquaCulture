import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Requires the separate model environment')
class GRUTests(unittest.TestCase):
    def test_training_scaling_constant_channel_and_initial_persistence(self):
        import torch
        from ml.modeling.gru import DOForecaster, fit_channel_scaling
        x = np.arange(72, dtype=np.float32).reshape(4, 6, 3) / 20
        x[:, :, 1] = 9.2
        mean, scale = fit_channel_scaling(x)
        self.assertEqual(scale[1], 1.)
        np.testing.assert_allclose(mean[0], x[:, :, 0].mean(), rtol=1e-6)
        model = DOForecaster(3, 8, mean, scale)
        np.testing.assert_array_equal(model(torch.tensor(x)).detach().numpy(), x[:, -1, 0])
        original = model.mean.clone()
        model(torch.tensor(x + 200))
        torch.testing.assert_close(model.mean, original)
        with self.assertRaises(ValueError):
            model(torch.zeros(4, 5, 3))

    def test_fit_restores_best_checkpoint_and_is_reproducible(self):
        import torch
        from ml.modeling.gru import load_checkpoint
        from ml.training.gru_fit import fit_replica
        x = np.linspace(6, 8, 120, dtype=np.float32).reshape(20, 6, 1)
        train = SimpleNamespace(x=x[:14], y=x[:14, -1, 0].astype(float) + .1)
        validation = SimpleNamespace(x=x[14:], y=x[14:, -1, 0].astype(float) + .1)
        settings = {'maximum_epochs': 3, 'patience': 2, 'batch_size': 4, 'weight_decay': .01, 'gradient_clip_norm': 1.}
        with tempfile.TemporaryDirectory() as directory:
            records = []
            for name in ['first', 'second']:
                path = Path(directory) / name
                result, predictions = fit_replica(train, validation, {'hidden_size': 8, 'learning_rate': .003},
                                                   settings, 17, 'cpu', path, 600, 10000, lambda _: None)
                model, record = load_checkpoint(path / 'best.pt')
                with torch.inference_mode():
                    actual = model(torch.tensor(validation.x)).numpy()
                np.testing.assert_array_equal(actual, predictions['validation'])
                self.assertEqual(record['epoch'], result['best_epoch'])
                self.assertLess(result['parameter_count'], 10000)
                records.append(predictions['validation'])
            np.testing.assert_array_equal(*records)
            with self.assertRaises(TimeoutError):
                fit_replica(train, validation, {'hidden_size': 8, 'learning_rate': .003}, settings, 17,
                            'cpu', Path(directory) / 'timeout', -1, 10000, lambda _: None)

    def test_cuda_forward_backward_checkpoint_and_cpu_inference(self):
        import torch
        if not torch.cuda.is_available():
            self.skipTest('CUDA hardware unavailable')
        from ml.modeling.gru import load_checkpoint
        from ml.training.gru_fit import fit_replica
        x = np.linspace(6, 8, 120, dtype=np.float32).reshape(20, 6, 1)
        train = SimpleNamespace(x=x[:14], y=x[:14, -1, 0].astype(float) + .1)
        validation = SimpleNamespace(x=x[14:], y=x[14:, -1, 0].astype(float) + .1)
        settings = {'maximum_epochs': 2, 'patience': 2, 'batch_size': 4, 'weight_decay': .01, 'gradient_clip_norm': 1.}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic-cuda'
            result, predictions = fit_replica(train, validation, {'hidden_size': 8, 'learning_rate': .003},
                                               settings, 17, 'cuda:0', path, 600, 10000, lambda _: None)
            self.assertGreater(result['peak_cuda_allocated_bytes'], 0)
            model, _ = load_checkpoint(path / 'best.pt', 'cpu')
            self.assertGreater(model.head.weight.abs().sum().item(), 0)
            with torch.inference_mode():
                cpu = model(torch.tensor(validation.x)).numpy()
            np.testing.assert_allclose(cpu, predictions['validation'], rtol=1e-6, atol=1e-6)

    def test_checkpoint_rejects_nonfinite_weights_and_unknown_contract(self):
        import torch
        from ml.modeling.gru import DOForecaster, load_checkpoint
        model = DOForecaster(1, 8, [7.], [1.])
        record = {'version': 'compact-do-gru-v1', 'history_hours': 6, 'features': 1, 'hidden_size': 8,
                  'state_dict': model.state_dict()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.pt'
            torch.save({**record, 'history_hours': 12}, path)
            with self.assertRaisesRegex(ValueError, 'contract'):
                load_checkpoint(path)
            record['state_dict']['head.weight'][0, 0] = float('nan')
            torch.save(record, path)
            with self.assertRaisesRegex(ValueError, 'Non-finite'):
                load_checkpoint(path)


if __name__ == '__main__':
    unittest.main()
