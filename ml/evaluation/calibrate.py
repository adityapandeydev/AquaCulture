"""Freeze the shipping candidate and its interval calibration before the test is opened."""
import argparse
import json
from pathlib import Path

from ml.data.files import digest
from ml.models.blend import blend, load_families, selected_artifacts
from ml.training.common import Development, provenance, write_json

from .conformal import apply_offsets, fit_offsets
from .metrics import quantile_metrics

AMENDMENT = Path('docs/models/amendment.json')


def run(simple, neural, output):
    if output.exists():
        raise FileExistsError('The candidate is already frozen: ' + str(output))
    plan = json.loads(AMENDMENT.read_text(encoding='utf-8'))
    info = provenance()
    if info['uncommitted_ml']:
        raise ValueError('Commit code and records before opening the calibration data')
    data, weights = Development(), plan['blend']['weights']
    artifacts = selected_artifacts(simple, neural)
    models = load_families(artifacts)
    forecasts = {s: {f: m.predict(v) for f, m in models.items()} for s, v in data.sets.items()}
    scores = {'blend': data.score({s: blend(f, weights) for s, f in forecasts.items()})[0],
              'trees': data.score({s: f['trees'] for s, f in forecasts.items()})[0]}
    for name, value in scores.items():
        if abs(value - plan['validation_scores'][name]) > 1e-4:
            raise ValueError(f'{name} validation score {value:.4f} differs from the amendment')
    print('Artifacts verified. Validation scores', {k: round(v, 4) for k, v in scores.items()}, flush=True)

    calibration = data.release.samples('calibration', reserved=True)
    families = {f: m.predict(calibration) for f, m in models.items()}
    pairs, candidates = plan['calibration']['pairs'], {}
    for name, raw in {'blend': blend(families, weights), 'trees': families['trees']}.items():
        offsets = fit_offsets(calibration.y, raw, data.quantiles, pairs)
        adjusted = apply_offsets(raw, data.quantiles, pairs, offsets)
        before, after = (quantile_metrics(calibration, f, data.quantiles) for f in (raw, adjusted))
        shown = {'calibration_coverage_before': [r['coverage'] for r in before],
                 'calibration_coverage_after': [r['coverage'] for r in after],
                 'calibration_width_after': [r['width'] for r in after]}
        candidates[name] = {'offsets_by_horizon_and_pair': offsets, **shown}
        print(name, {k: [round(x, 3) for x in v] for k, v in shown.items()}, flush=True)
    write_json(output, {'version': 'carp-forecast-candidate-v1', 'shipping_candidate': plan['shipping_candidate'],
                        'created_at_utc': info['created_at_utc'], 'git_revision': info['git_revision'],
                        'amendment_sha256': digest(AMENDMENT), 'criteria_sha256': info['criteria_sha256'],
                        'release_descriptor_sha256': info['release_descriptor_sha256'],
                        'artifacts': artifacts, 'weights': weights, 'quantiles': list(data.quantiles), 'pairs': pairs,
                        'calibration_windows': len(calibration), 'validation_scores': scores, 'candidates': candidates})
    print('Saved', output, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simple', type=Path, default=Path('ml/runs/carp-simple'))
    parser.add_argument('--neural', type=Path, default=Path('ml/runs/carp-neural'))
    parser.add_argument('--output', type=Path, default=Path('docs/models/candidate.json'))
    args = parser.parse_args()
    run(args.simple, args.neural, args.output)


if __name__ == '__main__':
    main()
