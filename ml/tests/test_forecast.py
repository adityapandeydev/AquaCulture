import unittest

import numpy as np
import pandas as pd

from ml.data.arrays import CarpRelease, assemble
from ml.evaluation.metrics import (alert_metrics, event_rate, point_metrics, probability_below, quantile_metrics,
                                   relative_score)
from ml.models.history import Samples, fill_history
from ml.models.naive import fit_profile, persistence, profile, yesterday
from ml.models.ridge import Ridge

QUANTILES = (0.02, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.98)


def synthetic(n=480, ponds=2, seed=0):
    """Ponds with a clean daily oxygen cycle."""
    rng = np.random.default_rng(seed)
    hour = np.arange(n) % 24
    wave = lambda h: 6 + 4 * np.sin(2 * np.pi * np.asarray(h) / 24)
    steps = hour[:, None] - np.arange(23, -1, -1)
    x = np.stack([wave(steps) + rng.normal(0, .1, steps.shape), np.full(steps.shape, 8.), np.full(steps.shape, 25.)], axis=2)
    y = np.stack([wave(hour + h) for h in (1, 3, 6, 12)], axis=1)
    pond = np.array([f'p{i % ponds}' for i in range(n)])
    return Samples(x, y, hour, pond, np.arange(n))


class ArraysTest(unittest.TestCase):
    def test_histories_stop_at_issue_and_stay_in_session(self):
        hours = pd.DataFrame({'pond_id': 'a', 'session': [0] * 30 + [1] * 30,
                              'hour': pd.date_range('2025-12-20', periods=60, freq='h'),
                              'do_mgL': np.arange(60.) + 1, 'ph': 8., 'temperature_c': 25., 'eligible': True})
        hours.loc[5, 'eligible'] = False
        issue = hours.hour[25]
        windows = pd.DataFrame({'pond_id': 'a', 'session': 0, 'issue_hour': issue, 'horizon_hours': [1, 3],
                                'target_hour': [issue + pd.Timedelta(hours=h) for h in (1, 3)]})
        s = assemble(hours, windows)
        self.assertEqual(s.last[0], 26.)
        self.assertEqual(s.x[0, 0, 0], 3.)
        self.assertTrue(np.isnan(s.x[0, 3, 0]))
        np.testing.assert_array_equal(s.y[0], [27., 29., np.nan, np.nan])
        early = windows.assign(session=1, issue_hour=hours.hour[35],
                               target_hour=[hours.hour[36], hours.hour[38]])
        history = assemble(hours, early).x[0, :, 0]
        self.assertEqual(np.isfinite(history).sum(), 6)

    def test_reserved_partitions_are_closed(self):
        release = CarpRelease.__new__(CarpRelease)
        release.anchor = {'reserved_partitions': ['calibration', 'test_unseen_pond']}
        for name in ['calibration', 'test_unseen_pond', 'unknown']:
            with self.assertRaises(PermissionError):
                release.samples(name)

    def test_fill_uses_only_the_same_history(self):
        x = np.array([[[np.nan], [2.], [np.nan], [4.]]])
        filled, present = fill_history(x)
        self.assertEqual(filled[0, :, 0].tolist(), [2., 2., 2., 4.])
        self.assertEqual(present[0, :, 0].tolist(), [False, True, False, True])
        self.assertTrue(np.isnan(fill_history(np.full((1, 3, 1), np.nan))[0]).all())


class ModelTest(unittest.TestCase):
    def test_naive_forecasts(self):
        s = synthetic()
        np.testing.assert_allclose(persistence(s)[:, 3], s.last)
        np.testing.assert_allclose(yesterday(s)[:, 0], s.x[:, 0, 0])
        np.testing.assert_allclose(yesterday(s)[:, 3], s.x[:, 11, 0])
        self.assertLess(np.abs(profile(s, fit_profile(s)) - s.y).mean(), .3)

    def test_yesterday_falls_back_to_latest(self):
        s = synthetic()
        s.x[0, 0, 0] = np.nan
        self.assertEqual(yesterday(s)[0, 0], s.last[0])

    def test_ridge_learns_the_cycle_and_orders_quantiles(self):
        s = synthetic()
        forecast = Ridge(1.0, QUANTILES).fit(s).predict(s)
        self.assertLess(np.abs(forecast[:, :, 4] - s.y).mean(), np.abs(persistence(s) - s.y).mean() * .2)
        self.assertTrue((np.diff(forecast, axis=2) >= 0).all())

    def test_trees_accept_missing_channels(self):
        try:
            from ml.models.trees import Trees
        except ImportError:
            self.skipTest('scikit-learn is not installed')
        s = synthetic()
        s.x[:5, :, 1] = np.nan
        forecast = Trees(7, 20, (0.1, 0.5, 0.9), iterations=20).fit(s).predict(s)
        self.assertEqual(forecast.shape, (len(s), 4, 3))
        self.assertTrue(np.isfinite(forecast).all())

    def test_networks_are_causal_shaped_and_ordered(self):
        try:
            import torch
            from ml.models.features import inputs
            from ml.models.network import QuantileNetwork, pinball
        except ImportError:
            self.skipTest('PyTorch is not installed')
        s = synthetic(64)
        s.x[0, :, 1] = np.nan
        values = inputs(s, np.array([6., 8., 25.]), np.array([3., 1., 1.]))
        self.assertTrue(np.isfinite(values).all())
        for kind in ['gru', 'tcn']:
            torch.manual_seed(1)
            model = QuantileNetwork(kind, 16, QUANTILES, 3.)
            out = model(torch.as_tensor(values), torch.as_tensor(s.last, dtype=torch.float32))
            self.assertEqual(tuple(out.shape), (64, 4, 9))
            self.assertTrue((torch.diff(out, dim=2) > 0).all())
            np.testing.assert_allclose(out[:, 0, 4].detach().numpy(), s.last, rtol=1e-5)
            target = torch.as_tensor(s.y, dtype=torch.float32)
            target[0] = float('nan')
            loss = pinball(out, target, torch.tensor(QUANTILES), 3.)
            loss.backward()
            self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))


class MetricsTest(unittest.TestCase):
    def test_ponds_count_equally(self):
        s = synthetic(4, ponds=1)
        s = Samples(s.x, np.zeros((4, 4)), s.hour, np.array(['a', 'a', 'a', 'b']), s.issue)
        forecast = np.zeros((4, 4))
        forecast[3] = 4.
        self.assertEqual(point_metrics(s, forecast)[0]['mae'], 2.)

    def test_missing_forecast_is_rejected(self):
        s = synthetic(8)
        forecast = np.zeros((8, 4))
        forecast[0, 0] = np.nan
        with self.assertRaises(ValueError):
            point_metrics(s, forecast)

    def test_coverage_and_probability(self):
        s = synthetic(48)
        offsets = np.array([-2., -1.5, -1., -.5, 0., .5, 1., 1.5, 2.])
        forecast = s.y[:, :, None] + offsets
        row = quantile_metrics(s, forecast, QUANTILES)[0]
        self.assertEqual((row['coverage'], row['width']), (1., 3.))
        self.assertAlmostEqual(probability_below(forecast[:1], QUANTILES, s.y[0, 0])[0, 0], .5, places=6)
        self.assertEqual(probability_below(forecast[:1], QUANTILES, -100.)[0, 0], .01)
        self.assertEqual(probability_below(forecast[:1], QUANTILES, 100.)[0, 0], .99)

    def test_alert_skill_is_positive_for_sharp_forecasts(self):
        s = synthetic(48)
        forecast = s.y[:, :, None] + np.linspace(-.1, .1, 9)
        row = alert_metrics(s, forecast, QUANTILES, 3., np.full(24, .2))[0]
        self.assertGreater(row['brier_skill'], .9)
        self.assertEqual(row['recall'], 1.)
        self.assertEqual(event_rate(s, 100.).tolist(), [1.] * 24)

    def test_score_uses_the_strongest_naive_model(self):
        naive = {'v': {'a': [2., 4., 4., 4.], 'b': [4., 2., 4., 4.]}}
        self.assertEqual(relative_score({'v': [1., 1., 2., 2.]}, naive), .5)


if __name__ == '__main__':
    unittest.main()
