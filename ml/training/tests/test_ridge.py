import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ml.modeling.ridge import RidgeForecaster, fit_ridge


class RidgeTests(unittest.TestCase):
    def data(self):
        return np.array([0., 1., 2.]).reshape(3, 1, 1), np.array([1., 3., 5.])

    def test_closed_form_ridge_and_unpenalized_intercept(self):
        x, y = self.data()
        model = fit_ridge(x, y, alpha=1.)
        np.testing.assert_allclose(model.predict(x), [1.5, 3., 4.5])
        np.testing.assert_allclose(model.mean, [1.])
        self.assertAlmostEqual(model.intercept, 3.)

    def test_validation_prediction_cannot_change_fitted_scaling(self):
        x, y = self.data()
        model = fit_ridge(x, y, alpha=1.)
        before = model.to_dict()
        model.predict(np.array([100., 200.]).reshape(2, 1, 1))
        self.assertEqual(before, model.to_dict())
        np.testing.assert_array_equal(x[:, 0, 0], [0., 1., 2.])

    def test_constant_feature_has_unit_scale_and_no_nan(self):
        x, y = self.data()
        x = np.concatenate([x, np.full_like(x, 9.)], axis=2)
        model = fit_ridge(x, y, alpha=1.)
        self.assertEqual(model.scale[1], 1.)
        self.assertEqual(model.coefficients[1], 0.)
        self.assertTrue(np.isfinite(model.predict(x)).all())

    def test_nonbinary_constant_features_do_not_gain_roundoff_variance(self):
        x = np.full((100, 6, 1), 9.2)
        model = fit_ridge(x, np.linspace(6., 8., 100), alpha=.1)
        np.testing.assert_array_equal(model.scale, np.ones(6))
        np.testing.assert_array_equal(model.coefficients, np.zeros(6))

    def test_json_roundtrip_and_existing_artifact_protection(self):
        x, y = self.data()
        model = fit_ridge(x, y, alpha=.1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.json'
            model.save(path)
            restored = RidgeForecaster.load(path)
            np.testing.assert_array_equal(restored.predict(x), model.predict(x))
            with self.assertRaises(FileExistsError):
                model.save(path)
            record = json.loads(path.read_text())
            record['scale'][0] = 0
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                RidgeForecaster.load(path)

    def test_wrong_shapes_nonfinite_values_and_invalid_alpha_fail(self):
        x, y = self.data()
        for alpha in [0., -1., float('inf'), float('nan')]:
            with self.assertRaises(ValueError):
                fit_ridge(x, y, alpha=alpha)
        with self.assertRaises(ValueError):
            fit_ridge(x, y[:2], alpha=1.)
        with self.assertRaises(ValueError):
            fit_ridge(np.full_like(x, np.nan), y, alpha=1.)
        model = fit_ridge(x, y, alpha=1.)
        with self.assertRaises(ValueError):
            model.predict(np.zeros((2, 2, 1)))


if __name__ == '__main__':
    unittest.main()
