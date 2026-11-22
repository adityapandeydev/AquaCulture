"""Private HTTP service for dissolved oxygen forecasts."""
import argparse
import hmac
import json
import logging
import os
from datetime import timedelta
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from ml.models.history import HISTORY, HORIZONS, Samples

from .engine import Bundle
from .schema import ForecastRequest, RequestError, local_zone, to_samples, utc_text

log = logging.getLogger('aquatech.model')
MAXIMUM_BODY = 64 * 1024
LOOPBACK = {'127.0.0.1', '::1', 'localhost'}


def failure(status, code, message, reasons=()):
    return JSONResponse({'error': {'code': code, 'message': message, 'reasons': list(reasons)}}, status_code=status)


def load_bundle(folder, anchor):
    """Load the bundle and compute one forecast so the first request is not slow."""
    released = json.loads(Path(anchor).read_text(encoding='utf-8'))['manifest_sha256']
    bundle = Bundle(folder, released)
    middle = [sum(v) / 2 for v in bundle.manifest['training_range'].values()]
    x = np.broadcast_to(np.array(middle), (1, HISTORY, len(middle))).copy()
    bundle.forecast(Samples(x, np.full((1, len(HORIZONS)), np.nan), np.array([6]), np.array(['']), np.array([0])))
    return bundle


def create_app(load, token=None):
    """Build the app. `load` returns a bundle. A failed load leaves the service alive but not ready."""
    app = FastAPI(title='AquaTech model service', docs_url=None, redoc_url=None, openapi_url=None)
    try:
        app.state.bundle = load()
    except Exception:
        log.exception('The model bundle could not be loaded')
        app.state.bundle = None

    @app.middleware('http')
    async def guard(request: Request, call_next):
        if request.url.path not in ('/health', '/ready'):
            if token:
                given = request.headers.get('authorization', '')
                if not hmac.compare_digest(given.encode(), f'Bearer {token}'.encode()):
                    return failure(401, 'unauthorized', 'A valid service token is required.')
            if request.method == 'POST':
                length = request.headers.get('content-length', '')
                if not length.isdigit():
                    return failure(411, 'length_required', 'Content-Length is required.')
                if int(length) > MAXIMUM_BODY:
                    return failure(413, 'request_too_large', 'The request body is too large.')
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def on_validation(request, error):
        reasons = sorted({'.'.join(str(p) for p in e['loc'][1:]) + ': ' + e['type'] for e in error.errors()})
        return failure(400, 'invalid_request', 'The request is not valid.', reasons[:20])

    @app.exception_handler(RequestError)
    async def on_request_error(request, error):
        return failure(error.status, error.code, error.message, error.reasons)

    @app.exception_handler(HTTPException)
    async def on_http_error(request, error):
        return failure(error.status_code, 'not_found' if error.status_code == 404 else 'request_failed', 'The request failed.')

    def ready():
        if app.state.bundle is None:
            raise RequestError(503, 'model_unavailable', 'No verified model is loaded.')
        return app.state.bundle

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.get('/ready')
    def readiness():
        return {'status': 'ready', 'model_id': ready().manifest['model_id']}

    @app.get('/v2/model')
    def model():
        bundle = ready()
        keys = ['model_id', 'species', 'scope', 'horizons_hours', 'released', 'alert_threshold_mgL',
                'training_range', 'training_months']
        return {**{k: bundle.manifest[k] for k in keys}, 'manifest_sha256': bundle.sha256}

    @app.post('/v2/forecasts')
    def forecasts(body: ForecastRequest):
        bundle = ready()
        if body.species not in bundle.manifest['species']:
            raise RequestError(422, 'unsupported_species', 'No forecast model is available for this species.')
        samples = to_samples(body)
        try:
            rows = bundle.forecast(samples)
        except Exception:
            log.exception('Forecast computation failed')
            raise RequestError(503, 'prediction_unavailable', 'The forecast could not be computed.')
        for row in rows:
            start = body.issue_time + timedelta(hours=row['horizon_hours'] - 1)
            row['target_start'], row['target_end'] = utc_text(start), utc_text(start + timedelta(hours=1))
        warnings = ['outside_training_range:' + c for c in bundle.outside_range(samples)]
        months = bundle.manifest['training_months']
        if body.issue_time.astimezone(local_zone(body.timezone)).month not in months:
            warnings.append('outside_training_season')
        return {'model_id': bundle.manifest['model_id'], 'manifest_sha256': bundle.sha256,
                'scope': bundle.manifest['scope'], 'issue_time': utc_text(body.issue_time),
                'forecasts': rows, 'warnings': warnings}

    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', default='ml/bundles/carp-1')
    parser.add_argument('--release', default='docs/models/release.json')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8100)
    args = parser.parse_args()
    token = os.environ.get('MODEL_TOKEN') or None
    if args.host not in LOOPBACK and not token:
        parser.error('Set MODEL_TOKEN before listening outside this machine')
    uvicorn.run(create_app(lambda: load_bundle(args.bundle, args.release), token), host=args.host, port=args.port,
                limit_concurrency=64)


if __name__ == '__main__':
    main()
