"""Package the tested blend as a bundle without pickle, PyTorch or scikit-learn."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from ml.data.files import digest
from ml.evaluation.conformal import apply_offsets
from ml.models.blend import blend, load_families
from ml.models.features import INPUTS
from ml.models.history import CHANNELS, HISTORY, HORIZONS
from ml.service.engine import VERSION, Bundle

from .common import Development, write_json

CANDIDATE, RELEASE = Path('docs/models/candidate.json'), Path('docs/models/release.json')
TOLERANCE = 1e-4


def save_ridge(model, path):
    np.savez_compressed(path, mean=model.mean, scale=model.scale, weights=np.stack(model.weights),
                        residuals=np.stack(model.residuals))


def save_trees(model, path):
    """Flatten every tree. Leaves point to themselves, so a fixed number of steps reaches them."""
    parts = {k: [] for k in ('feature', 'threshold', 'value', 'left', 'right', 'missing_left')}
    offset, depth, roots, baseline = 0, 0, [], []
    for row in model.models:
        for fitted in row:
            baseline.append(float(fitted._baseline_prediction.ravel()[0]))
            for (tree,) in fitted._predictors:
                nodes = tree.nodes
                if nodes['is_categorical'].any():
                    raise ValueError('Categorical splits are not supported')
                leaf, own = nodes['is_leaf'].astype(bool), np.arange(len(nodes))
                roots.append(offset)
                depth = max(depth, int(nodes['depth'].max()))
                parts['feature'].append(np.where(leaf, 0, nodes['feature_idx']).astype(np.int16))
                parts['threshold'].append(np.where(leaf, np.inf, nodes['num_threshold']))
                parts['value'].append(np.where(leaf, nodes['value'], 0.))
                parts['left'].append((np.where(leaf, own, nodes['left']) + offset).astype(np.int32))
                parts['right'].append((np.where(leaf, own, nodes['right']) + offset).astype(np.int32))
                parts['missing_left'].append(nodes['missing_go_to_left'].astype(bool))
                offset += len(nodes)
    shape = (len(model.models), len(model.models[0]))
    np.savez_compressed(path, roots=np.array(roots, dtype=np.int32).reshape(*shape, -1), depth=depth,
                        baseline=np.array(baseline).reshape(shape), **{k: np.concatenate(v) for k, v in parts.items()})


def save_network(model, path):
    example = (torch.zeros(2, HISTORY, INPUTS), torch.ones(2))
    torch.onnx.export(model.cpu().eval(), example, str(path), input_names=['x', 'last'], output_names=['forecast'],
                      dynamic_axes={k: {0: 'batch'} for k in ('x', 'last', 'forecast')}, opset_version=17, dynamo=False)


def released_flags(final):
    return {h: {k: g['passed'] for k, g in checks.items()} for h, checks in final['gates']['blend'].items()}


def run(output, final_run, name):
    if output.exists():
        raise FileExistsError('Use a new bundle directory: ' + str(output))
    candidate = json.loads(CANDIDATE.read_text(encoding='utf-8'))
    final = json.loads((final_run / 'run.json').read_text(encoding='utf-8'))
    # The test recorded this file with Windows line endings.
    accepted = {digest(CANDIDATE), hashlib.sha256(CANDIDATE.read_bytes().replace(b'\n', b'\r\n')).hexdigest()}
    if final['candidate_sha256'] not in accepted:
        raise ValueError('The final test was not run on this candidate')
    models, data = load_families(candidate['artifacts']), Development()
    output.mkdir(parents=True)
    save_ridge(models['ridge'], output / 'ridge.npz')
    save_trees(models['trees'], output / 'trees.npz')
    networks, scaling = {}, None
    for family in ('gru', 'tcn'):
        networks[family] = []
        for number, (model, mean, scale) in enumerate(models[family].members, 1):
            current = {'mean': mean.tolist(), 'scale': scale.tolist()}
            if scaling not in (None, current):
                raise ValueError('Networks use different scaling')
            scaling = current
            networks[family].append(f'{family}{number}.onnx')
            save_network(model, output / networks[family][-1])
    rows = data.fit.x.reshape(-1, len(CHANNELS))
    files = ['ridge.npz', 'trees.npz', *networks['gru'], *networks['tcn']]
    write_json(output / 'manifest.json', {
        'version': VERSION, 'model_id': name, 'species': ['rohu_catla'], 'scope': 'research_and_demonstration',
        'horizons_hours': list(HORIZONS), 'quantiles': candidate['quantiles'], 'weights': candidate['weights'],
        'pairs': candidate['pairs'], 'offsets': candidate['candidates']['blend']['offsets_by_horizon_and_pair'],
        'released': released_flags(final), 'alert_threshold_mgL': data.criteria['alert_gates']['gated_threshold_mgL'],
        'networks': networks, 'scaling': scaling, 'training_months': [11, 12, 1],
        'training_range': {c: [float(np.nanmin(rows[:, i])), float(np.nanmax(rows[:, i]))] for i, c in enumerate(CHANNELS)},
        'candidate_sha256': final['candidate_sha256'], 'final_run_sha256': digest(final_run / 'run.json'),
        'files_sha256': {f: digest(output / f) for f in files}})

    bundle, worst = Bundle(output), 0.
    for key, samples in data.sets.items():
        original = apply_offsets(blend({f: m.predict(samples) for f, m in models.items()}, candidate['weights']),
                                 data.quantiles, candidate['pairs'], candidate['candidates']['blend']['offsets_by_horizon_and_pair'])
        worst = max(worst, float(np.abs(bundle.quantile_forecast(samples) - original).max()))
        print(f'{key}: {len(samples)} histories, largest difference so far {worst:.2e} mg/L', flush=True)
    if worst > TOLERANCE:
        raise ValueError('Bundle forecasts differ from the tested models')
    size = sum(f.stat().st_size for f in output.iterdir()) / 2 ** 20
    write_json(RELEASE, {'model_id': name, 'local_bundle': output.as_posix(), 'manifest_sha256': bundle.sha256,
                         'files_sha256': bundle.manifest['files_sha256'], 'released': bundle.manifest['released'],
                         'size_mib': round(size, 2), 'parity_max_mgL': worst, 'final_run_sha256': bundle.manifest['final_run_sha256']})
    print(f'Saved {output} ({size:.1f} MiB) and {RELEASE}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('ml/bundles/carp-1'))
    parser.add_argument('--final', type=Path, default=Path('ml/runs/carp-final'))
    parser.add_argument('--name', default='carp-blend-1')
    args = parser.parse_args()
    run(args.output, args.final, args.name)


if __name__ == '__main__':
    main()
