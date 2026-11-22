import copy
import json
import unittest
from pathlib import Path

import numpy as np

from ml.data.arrays import Samples
from ml.evaluation.conformal import apply_offsets, fit_offsets
from ml.evaluation.final import evaluate, gates
from ml.evaluation.metrics import alert_metrics, gain_interval
from ml.models.blend import blend
from ml.models.naive import fit_profile

from .test_forecast import QUANTILES, synthetic

PAIRS = [[0.02, 0.98], [0.05, 0.95], [0.1, 0.9], [0.25, 0.75]]
CRITERIA = json.loads(Path('docs/models/criteria.json').read_text(encoding='utf-8'))


def dated():
    s = synthetic(96)
    issue = np.datetime64('2026-01-24') + np.arange(96).astype('timedelta64[h]')
    return Samples(s.x, s.y, s.hour, s.pond, issue)


class ConformalTest(unittest.TestCase):
    def test_offsets_restore_coverage_and_keep_the_median(self):
        rng = np.random.default_rng(3)
        y = rng.normal(10, 1, (2000, 4))
        forecast = np.broadcast_to(10 + np.linspace(-.8, .8, 9), (2000, 4, 9)).copy()
        offsets = fit_offsets(y[:1000], forecast[:1000], QUANTILES, PAIRS)
        out = apply_offsets(forecast[1000:], QUANTILES, PAIRS, offsets)
        inside = (y[1000:] >= out[:, :, 1]) & (y[1000:] <= out[:, :, 7])
        self.assertTrue((np.abs(inside.mean(axis=0) - .9) < .03).all())
        np.testing.assert_array_equal(out[:, :, 4], forecast[1000:, :, 4])
        self.assertTrue((np.diff(out, axis=2) >= 0).all())

    def test_shrinking_offsets_cannot_cross(self):
        forecast = np.broadcast_to(5 + np.linspace(-1, 1, 9), (3, 4, 9)).copy()
        out = apply_offsets(forecast, QUANTILES, PAIRS, [[-5.] * 4] * 4)
        self.assertTrue((np.diff(out, axis=2) >= 0).all())
        np.testing.assert_array_equal(out[:, :, 4], forecast[:, :, 4])

    def test_small_calibration_sets_are_rejected(self):
        with self.assertRaises(ValueError):
            fit_offsets(np.zeros((5, 1)), np.zeros((5, 1, 9)), QUANTILES, PAIRS)


class FinalTest(unittest.TestCase):
    def test_blend_weights(self):
        f = {'a': np.ones(3), 'b': np.full(3, 3.)}
        np.testing.assert_array_equal(blend(f, {'a': .5, 'b': .5}), np.full(3, 2.))
        with self.assertRaises(ValueError):
            blend(f, {'a': .5, 'b': .6})

    def test_onset_ignores_hours_already_low(self):
        s = synthetic(96)
        forecast = s.y[:, :, None] + np.linspace(-.1, .1, 9)
        every = alert_metrics(s, forecast, QUANTILES, 3., np.full(24, .2))[0]
        onset = alert_metrics(s, forecast, QUANTILES, 3., np.full(24, .2), onset=True)[0]
        self.assertGreater(every['events'], onset['events'])
        self.assertGreater(onset['events'], 0)

    def test_gain_interval_brackets_a_constant_gain(self):
        s = dated()
        low, high = gain_interval(s, s.y + .5, s.y + 1., resamples=50)[0]
        self.assertAlmostEqual(low, .5)
        self.assertAlmostEqual(high, .5)

    def test_gates_report_each_failure(self):
        s = dated()
        rates = {t: np.full(24, .2) for t in (2., 3.)}
        noise = np.random.default_rng(0).normal(0, .02, s.y.shape)
        forecast = (s.y + noise)[:, :, None] + np.linspace(-.04, .04, 9)
        report = evaluate(s, forecast, QUANTILES, fit_profile(s), rates)
        self.assertTrue(gates(report, CRITERIA)['1']['point']['passed'])
        worse = copy.deepcopy(report)
        worse['point'][0].update(gain=.049, bias=-.6)
        worse['quantile'][1]['coverage'] = .97
        result = gates(worse, CRITERIA)
        self.assertEqual(result['1']['point']['failed'], ['gain', 'bias'])
        self.assertEqual(result['3']['interval']['failed'], ['coverage'])


if __name__ == '__main__':
    unittest.main()
