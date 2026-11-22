"""Fit and compare naive, ridge and boosted-tree forecasts on the validation sets (CPU)."""
import argparse
import pickle
import time
from pathlib import Path

import numpy as np

from ml.data.files import digest
from ml.models.naive import naive_forecasts
from ml.models.ridge import Ridge

from .common import Development, provenance, summary, write_json

RIDGE = [{'alpha': a} for a in (1.0, 10.0, 100.0, 1000.0)]
TREES = [{'leaves': l, 'leaf_size': s} for l in (15, 31) for s in (50, 200)]


def families(quantiles):
    from ml.models.trees import Trees
    return {'ridge': (RIDGE, lambda s: Ridge(quantiles=quantiles, **s)),
            'trees': (TREES, lambda s: Trees(quantiles=quantiles, **s))}


def run(output):
    if output.exists():
        raise FileExistsError('Use a new run directory: ' + str(output))
    record = {'kind': 'carp-simple', **provenance()}
    data = Development()
    print(f'fit {len(data.fit)} | ' + ' | '.join(f'{k} {len(v)}' for k, v in data.sets.items()), flush=True)
    output.mkdir(parents=True)
    record['naive'] = {}
    for name in data.criteria['naive_models']:
        forecasts = {s: np.repeat(naive_forecasts(v, data.profile)[name][:, :, None], len(data.quantiles), axis=2)
                     for s, v in data.sets.items()}
        score, points = data.score(forecasts)
        record['naive'][name] = {'score': score, 'point': points}
        print(f'{name:12s} score {score:.4f} | {summary(points)}', flush=True)
    for family, (settings, make) in families(data.quantiles).items():
        trials = []
        for setting in settings:
            started = time.perf_counter()
            model = make(setting).fit(data.fit)
            details = data.details({s: model.predict(v) for s, v in data.sets.items()})
            trials.append({'settings': setting, 'seconds': time.perf_counter() - started, **details})
            print(f'{family:12s} score {details["score"]:.4f} {setting} {trials[-1]["seconds"]:.0f}s | {summary(details["point"])}', flush=True)
            if details['score'] == min(t['score'] for t in trials):
                path = output / f'{family}.pkl'
                path.write_bytes(pickle.dumps(model))
        best = min(trials, key=lambda t: t['score'])
        record[family] = {'trials': trials, 'selected': best['settings'], 'score': best['score'],
                          'artifact': f'{family}.pkl', 'artifact_sha256': digest(output / f'{family}.pkl')}
    write_json(output / 'run.json', record)
    print('Saved', output / 'run.json', flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)


if __name__ == '__main__':
    main()
