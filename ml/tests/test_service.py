import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

try:
    from fastapi.testclient import TestClient
    from ml.service.app import MAXIMUM_BODY, create_app, load_bundle
    from ml.service.engine import Bundle, BundleError
    from ml.service.schema import ForecastRequest, RequestError, to_samples
except ImportError as error:
    raise unittest.SkipTest('Service packages are not installed: ' + str(error))

BUNDLE, RELEASE = Path('ml/bundles/carp-1'), Path('docs/models/release.json')
IST = timezone(timedelta(hours=5, minutes=30))
ISSUE = datetime(2026, 1, 24, 6, tzinfo=IST)


def request(hours=24, issue=ISSUE, **changes):
    history = [{'start': (issue - timedelta(hours=k)).isoformat(), 'coverage': 1.0,
                'do_mgL': 6 + 3 * np.sin(2 * np.pi * ((issue - timedelta(hours=k)).hour - 8) / 24),
                'ph': 8.4, 'temperature_c': 26.0} for k in range(hours, 0, -1)]
    return {'species': 'rohu_catla', 'timezone': 'Asia/Kolkata', 'issue_time': issue.isoformat(), 'history': history, **changes}


class FakeBundle:
    sha256 = 'a' * 64
    manifest = {'model_id': 'fake', 'species': ['rohu_catla'], 'scope': 'test', 'horizons_hours': [1, 3, 6, 12], 'released': {},
                'alert_threshold_mgL': 3.0, 'training_months': [11, 12, 1], 'training_range': {'do_mgL': [0.1, 20]}}
    error = None

    def forecast(self, samples):
        if self.error:
            raise self.error
        return [{'horizon_hours': h, 'point_mgL': 1.0} for h in (1, 3, 6, 12)]

    def outside_range(self, samples):
        return ['do_mgL']


def client(load=FakeBundle, token=None):
    return TestClient(create_app(load, token), raise_server_exceptions=False)


class SchemaTest(unittest.TestCase):
    def samples(self, **changes):
        return to_samples(ForecastRequest(**request(**changes)))

    def test_grid_hour_and_order(self):
        s = self.samples()
        self.assertEqual(int(s.hour[0]), 5)
        self.assertTrue(np.isfinite(s.x).all())
        body = request()
        self.assertAlmostEqual(s.x[0, -1, 0], body['history'][-1]['do_mgL'])

    def test_low_coverage_counts_as_missing(self):
        body = request()
        body['history'][5]['coverage'] = 0.5
        s = to_samples(ForecastRequest(**body))
        self.assertTrue(np.isnan(s.x[0, 5]).all())

    def reasons(self, body):
        with self.assertRaises(RequestError) as caught:
            to_samples(ForecastRequest(**body))
        return caught.exception.reasons

    def test_history_limits(self):
        self.assertEqual(self.reasons(request(hours=19)),
                         ['insufficient_do_history', 'insufficient_ph_history', 'insufficient_temperature_history'])
        body = request()
        body['history'][-2]['do_mgL'] = None
        self.assertEqual(self.reasons(body), ['recent_do_gap'])
        body = request()
        for item in body['history'][:5]:
            item['ph'] = None
        self.assertEqual(self.reasons(body), ['insufficient_ph_history'])

    def test_time_errors(self):
        for change, reason in [({'issue_time': '2026-01-24T06:00:00Z'}, 'issue_time_not_on_local_hour'),
                               ({'timezone': 'Mars/Base'}, 'unknown_timezone'), ({'timezone': '../etc'}, 'unknown_timezone')]:
            self.assertEqual(self.reasons(request(**change)), [reason])
        body = request()
        body['history'][3], body['history'][4] = body['history'][4], body['history'][3]
        self.assertEqual(self.reasons(body), ['history_not_in_order'])
        body = request()
        body['history'][-1]['start'] = ISSUE.isoformat()
        self.assertEqual(self.reasons(body), ['history_after_issue_time'])
        body = request()
        body['history'][0]['start'] = (ISSUE - timedelta(hours=25)).isoformat()
        self.assertEqual(self.reasons(body), ['history_too_old'])
        body = request()
        body['history'][0]['start'] = (ISSUE - timedelta(hours=24, minutes=-7)).isoformat()
        self.assertEqual(self.reasons(body), ['history_not_on_hour_grid'])


class ApiTest(unittest.TestCase):
    def test_success_carries_identity_times_and_warnings(self):
        result = client().post('/v2/forecasts', json=request())
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body['issue_time'], '2026-01-24T00:30:00Z')
        self.assertEqual(body['forecasts'][0]['target_start'], '2026-01-24T00:30:00Z')
        self.assertEqual(body['forecasts'][3]['target_end'], '2026-01-24T12:30:00Z')
        self.assertEqual(body['warnings'], ['outside_training_range:do_mgL'])

    def test_season_warning(self):
        body = client().post('/v2/forecasts', json=request(issue=datetime(2026, 6, 1, 6, tzinfo=IST))).json()
        self.assertIn('outside_training_season', body['warnings'])

    def check(self, result, status, code):
        self.assertEqual(result.status_code, status)
        self.assertEqual(result.json()['error']['code'], code)
        self.assertNotIn('forecasts', result.json())

    def test_invalid_requests(self):
        api = client()
        self.check(api.post('/v2/forecasts', json=request(species='vannamei')), 422, 'unsupported_species')
        self.check(api.post('/v2/forecasts', json=request(extra=1)), 400, 'invalid_request')
        self.check(api.post('/v2/forecasts', json=request(history=[])), 400, 'invalid_request')
        self.check(api.post('/v2/forecasts', json=request(issue_time='2026-01-24T06:00:00')), 400, 'invalid_request')
        self.check(api.post('/v2/forecasts', content=b'{', headers={'content-type': 'application/json'}), 400, 'invalid_request')
        for value in (-1, 41, 'NaN', 'Infinity'):
            body = request()
            body['history'][0]['do_mgL'] = value
            self.check(api.post('/v2/forecasts', json=body), 400, 'invalid_request')
        self.check(api.post('/v2/forecasts', content=b'x' * (MAXIMUM_BODY + 1)), 413, 'request_too_large')
        self.check(api.get('/missing'), 404, 'not_found')

    def test_token(self):
        api = client(token='secret')
        self.check(api.post('/v2/forecasts', json=request()), 401, 'unauthorized')
        self.check(api.get('/v2/model'), 401, 'unauthorized')
        self.assertEqual(api.get('/health').status_code, 200)
        self.assertEqual(api.get('/v2/model', headers={'Authorization': 'Bearer secret'}).status_code, 200)

    def test_failed_load_is_alive_but_not_ready(self):
        def broken():
            raise BundleError('bad')
        api = client(broken)
        self.assertEqual(api.get('/health').status_code, 200)
        self.check(api.get('/ready'), 503, 'model_unavailable')
        self.check(api.post('/v2/forecasts', json=request()), 503, 'model_unavailable')

    def test_computation_failure_hides_details(self):
        fake = FakeBundle()
        fake.error = ArithmeticError('internal detail')
        result = client(lambda: fake).post('/v2/forecasts', json=request())
        self.check(result, 503, 'prediction_unavailable')
        self.assertNotIn('internal detail', result.text)


@unittest.skipUnless(BUNDLE.is_dir(), 'The exported bundle is not on this machine')
class BundleTest(unittest.TestCase):
    def test_only_accepted_outputs_are_released(self):
        body = client(lambda: load_bundle(BUNDLE, RELEASE)).post('/v2/forecasts', json=request()).json()
        rows = {r['horizon_hours']: r for r in body['forecasts']}
        self.assertEqual({h: r['point_mgL'] is not None for h, r in rows.items()}, {1: True, 3: True, 6: True, 12: False})
        self.assertEqual({h: r['interval_90'] is not None for h, r in rows.items()}, {1: True, 3: False, 6: False, 12: False})
        self.assertTrue(all(0 < r['low_oxygen']['probability'] < 1 for r in rows.values()))
        self.assertEqual(rows[12]['withheld'], ['point', 'interval'])
        self.assertLess(rows[1]['interval_90']['low_mgL'], rows[1]['point_mgL'])
        self.assertLess(rows[1]['point_mgL'], rows[1]['interval_90']['high_mgL'])

    def test_changed_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / 'b'
            shutil.copytree(BUNDLE, copy)
            expected = json.loads(RELEASE.read_text(encoding='utf-8'))['manifest_sha256']
            Bundle(copy, expected)
            (copy / 'ridge.npz').write_bytes(b'changed')
            with self.assertRaisesRegex(BundleError, 'ridge.npz'):
                Bundle(copy, expected)
            manifest = copy / 'manifest.json'
            manifest.write_bytes(manifest.read_bytes() + b' ')
            with self.assertRaisesRegex(BundleError, 'manifest'):
                Bundle(copy, expected)


if __name__ == '__main__':
    unittest.main()
