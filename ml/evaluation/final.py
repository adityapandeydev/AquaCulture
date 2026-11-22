"""One-time test of the frozen candidate and its comparison model."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ml.data.files import digest
from ml.models.blend import blend, load_families
from ml.models.history import HORIZONS
from ml.models.naive import naive_forecasts
from ml.training.common import CRITERIA, DESCRIPTOR, Development, provenance, write_json

from .calibrate import AMENDMENT
from .conformal import apply_offsets
from .metrics import alert_metrics, event_rate, gain_interval, point_metrics, quantile_metrics

CANDIDATE = Path('docs/models/candidate.json')


def evaluate(samples, forecast, quantiles, profile, rates):
    """Full report for one calibrated forecast on one test set."""
    middle = list(quantiles).index(0.5)
    naive = naive_forecasts(samples, profile)
    references = {k: point_metrics(samples, f) for k, f in naive.items()}
    strongest = [min(naive, key=lambda k: references[k][j]['mae']) for j in range(len(HORIZONS))]
    reference = np.stack([naive[k][:, j] for j, k in enumerate(strongest)], axis=1)
    point = point_metrics(samples, forecast[:, :, middle])
    intervals = gain_interval(samples, forecast[:, :, middle], reference)
    for j, row in enumerate(point):
        base = references[strongest[j]][j]
        row.update({'strongest_naive': strongest[j], 'naive_mae': base['mae'], 'gain': 1 - row['mae'] / base['mae'],
                    'gain_interval': intervals[j],
                    'pond_ratio': {p: v / base['pond_mae'][p] for p, v in row['pond_mae'].items()}})
    alerts = {f'{t:g}': {'all': alert_metrics(samples, forecast, quantiles, t, r),
                         'onset': alert_metrics(samples, forecast, quantiles, t, r, onset=True)}
              for t, r in rates.items()}
    return {'windows': len(samples), 'point': point, 'alerts': alerts,
            'quantile': quantile_metrics(samples, forecast, quantiles)}


def gates(report, criteria):
    """Apply the registered limits to one report."""
    point, interval, alert = criteria['point_gates'], criteria['interval_gates'], criteria['alert_gates']
    low, high = interval['pond_macro_coverage']
    result = {}
    for j, horizon in enumerate(HORIZONS):
        p, q, key = report['point'][j], report['quantile'][j], str(horizon)
        a = report['alerts'][f"{alert['gated_threshold_mgL']:g}"]['all'][j]
        checks = {
            'point': {'gain': p['gain'] >= point['minimum_mae_gain_over_strongest_naive'][key],
                      'ponds': max(p['pond_ratio'].values()) <= point['maximum_pond_mae_ratio_to_strongest_naive'],
                      'bias': abs(p['bias']) <= point['maximum_absolute_bias_mgL'][key]},
            'interval': {'coverage': low <= q['coverage'] <= high,
                         'ponds': min(q['pond_coverage'].values()) >= interval['minimum_pond_coverage']},
            'alert': {'events': a['events'] >= alert['minimum_events_to_assess'],
                      'brier_skill': a['brier_skill'] is not None and a['brier_skill'] > alert['minimum_brier_skill']}}
        result[key] = {name: {'passed': all(c.values()), 'failed': [k for k, v in c.items() if not v]}
                       for name, c in checks.items()}
    return result


def verify(candidate):
    expected = {AMENDMENT: candidate['amendment_sha256'], CRITERIA: candidate['criteria_sha256'],
                DESCRIPTOR: candidate['release_descriptor_sha256']}
    changed = [str(p) for p, value in expected.items() if digest(p) != value]
    if changed:
        raise ValueError('Frozen inputs changed: ' + ', '.join(changed))


def run(output, candidate_path=CANDIDATE):
    if output.exists():
        raise FileExistsError('Use a new output directory: ' + str(output))
    candidate = json.loads(candidate_path.read_text(encoding='utf-8'))
    verify(candidate)
    info = provenance()
    if info['uncommitted_ml']:
        raise ValueError('Commit code and records before opening the test')
    data, models = Development(), load_families(candidate['artifacts'])
    criteria = data.criteria
    rates = {t: event_rate(data.fit, t) for t in criteria['alert_gates']['thresholds_mgL']}
    output.mkdir(parents=True)
    record = {'version': 'carp-forecast-final-v1', 'candidate_sha256': digest(candidate_path), **info}
    write_json(output / 'attempt.json', {**record, 'test_opened_at_utc': datetime.now(timezone.utc).isoformat()})

    record['sets'], saved = {}, {}
    for name in [criteria['primary_test'], *criteria['secondary_tests']]:
        samples = data.release.samples(name, reserved=True)
        families = {f: m.predict(samples) for f, m in models.items()}
        raw = {'blend': blend(families, candidate['weights']), 'trees': families['trees']}
        record['sets'][name] = {}
        for model, forecast in raw.items():
            calibrated = apply_offsets(forecast, data.quantiles, candidate['pairs'],
                                       candidate['candidates'][model]['offsets_by_horizon_and_pair'])
            record['sets'][name][model] = evaluate(samples, calibrated, data.quantiles, data.profile, rates)
            saved[f'{name}_{model}'] = calibrated
        for key in ('y', 'pond', 'issue', 'last'):
            saved[f'{name}_{key}'] = getattr(samples, key)
        print('Scored', name, len(samples), flush=True)
    np.savez_compressed(output / 'forecasts.npz', **saved)
    record['gates'] = {m: gates(record['sets'][criteria['primary_test']][m], criteria) for m in ('blend', 'trees')}
    record['forecasts_sha256'] = digest(output / 'forecasts.npz')
    write_json(output / 'run.json', record)
    print(json.dumps(record['gates'], indent=1), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)


if __name__ == '__main__':
    main()
