"""Search GRU and TCN quantile forecasters on the GPU. Finished fits are skipped on resume."""
import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch

from ml.data.arrays import CHANNELS
from ml.data.files import digest
from ml.models.network import QuantileNetwork, load_network, pinball, predict, tensors

from .common import Development, provenance, summary, write_json

SETTINGS = {kind: [{'width': w, 'weight_decay': d} for w in (32, 64) for d in (1e-4, 1e-2)] for kind in ('gru', 'tcn')}
BATCH, RATE = 128, 1e-3


def scaling(samples):
    rows = samples.x.reshape(-1, len(CHANNELS))
    return np.nanmean(rows, axis=0), np.nanstd(rows, axis=0)


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def fit_one(kind, setting, seed, data, arrays, mean, scale, device, epochs, patience, label):
    """Train one network and keep the epoch with the best validation score."""
    seed_everything(seed)
    model = QuantileNetwork(kind, setting['width'], data.quantiles, scale[0]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=RATE, weight_decay=setting['weight_decay'])
    quantiles = torch.tensor(data.quantiles, dtype=torch.float32, device=device)
    x, last, y = arrays['fit']
    best, state, history = None, None, []
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        order, total = torch.randperm(len(x), device=device), 0.
        for rows in order.split(BATCH):
            loss = pinball(model(x[rows], last[rows]), y[rows], quantiles, float(scale[0]))
            if not torch.isfinite(loss):
                raise RuntimeError('Training loss is not finite')
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += loss.item() * len(rows)
        forecasts = {s: predict(model, *arrays[s][:2]) for s in data.sets}
        score, points = data.score(forecasts)
        history.append({'epoch': epoch, 'loss': total / len(x), 'score': score})
        if best is None or score < best['score']:
            best = {'epoch': epoch, 'score': score, 'point': points}
            state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if epoch % 5 == 0 or epoch == 1:
            print(f'{label} epoch {epoch:3d} loss {total / len(x):.4f} score {score:.4f} best {best["score"]:.4f} '
                  f'@{best["epoch"]} {time.perf_counter() - started:.0f}s', flush=True)
        if epoch - best['epoch'] >= patience:
            break
    return state, {**best, 'epochs_run': epoch, 'seconds': time.perf_counter() - started, 'history': history,
                   'parameters': sum(p.numel() for p in model.parameters())}


def check_resume(output, identity):
    """A resumed run must use the same code, criteria, data and options."""
    path = output / 'setup.json'
    if path.exists():
        saved = json.loads(path.read_text(encoding='utf-8'))
        keys = ['source_sha256', 'criteria_sha256', 'release_descriptor_sha256', 'options']
        if any(saved[k] != identity[k] for k in keys):
            raise ValueError('Code, data or options changed since this run started. Use a new output directory.')
        return saved
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Output directory is not empty and is not a neural run')
    output.mkdir(parents=True, exist_ok=True)
    write_json(path, identity)
    return identity


def run(output, device, epochs=None, kinds=None, limit=None):
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable. Training does not fall back to the CPU.')
    data = Development()
    rules = data.criteria['selection']
    epochs = epochs or rules['maximum_epochs']
    kinds = kinds or list(SETTINGS)
    options = {'device': device, 'epochs': epochs, 'kinds': kinds, 'limit': limit, 'batch': BATCH, 'rate': RATE}
    record = check_resume(output, {'kind': 'carp-neural', 'options': options, **provenance(),
                                   'device_name': torch.cuda.get_device_name(0) if device == 'cuda' else 'cpu'})
    mean, scale = scaling(data.fit)
    arrays = {'fit': tensors(data.fit, mean, scale, device)}
    arrays.update({s: tensors(v, mean, scale, device) for s, v in data.sets.items()})
    plan = [(k, i, s) for k in kinds for i in range(len(SETTINGS[k][:limit])) for s in rules['seeds']]
    print(f'{record["device_name"]} | fit {len(data.fit)} | {len(plan)} fits, at most {epochs} epochs each', flush=True)
    for number, (kind, index, seed) in enumerate(plan, 1):
        folder = output / kind / f'setting{index + 1}'
        result, weights = folder / f'seed{seed}.json', folder / f'seed{seed}.pt'
        label = f'[{number}/{len(plan)}] {kind} setting {index + 1} seed {seed}'
        if result.exists() and weights.exists():
            print(label, 'already finished', flush=True)
            continue
        folder.mkdir(parents=True, exist_ok=True)
        setting = SETTINGS[kind][index]
        state, fitted = fit_one(kind, setting, seed, data, arrays, mean, scale, device, epochs, rules['patience'], label)
        torch.save({'kind': kind, 'width': setting['width'], 'quantiles': list(data.quantiles), 'state': state,
                    'mean': mean.tolist(), 'scale': scale.tolist(), 'seed': seed}, weights)
        write_json(result, {'settings': setting, 'seed': seed, 'weights_sha256': digest(weights), **fitted})
        print(f'{label} done: score {fitted["score"]:.4f} at epoch {fitted["epoch"]} | {summary(fitted["point"])}', flush=True)
    finish(output, record, data, arrays, kinds, limit, rules['seeds'], device)


def finish(output, record, data, arrays, kinds, limit, seeds, device):
    """Score each setting as the registered three-seed mean and select one per family."""
    report = {**record, 'families': {}}
    for kind in kinds:
        trials = []
        for index, setting in enumerate(SETTINGS[kind][:limit]):
            folder, members, artifacts = output / kind / f'setting{index + 1}', [], {}
            for seed in seeds:
                path = folder / f'seed{seed}.pt'
                saved = json.loads((folder / f'seed{seed}.json').read_text(encoding='utf-8'))
                if digest(path) != saved['weights_sha256']:
                    raise ValueError('Saved weights changed: ' + str(path))
                artifacts[f'{kind}/setting{index + 1}/seed{seed}.pt'] = saved['weights_sha256']
                model, _, _ = load_network(path, device)
                members.append({s: predict(model, *arrays[s][:2]) for s in data.sets})
            mixed = {s: np.mean([m[s] for m in members], axis=0) for s in data.sets}
            trials.append({'settings': setting, 'artifacts': artifacts, **data.details(mixed),
                           'seed_scores': [data.score(m)[0] for m in members]})
            print(f'{kind} setting {index + 1} three-seed mean: score {trials[-1]["score"]:.4f} | {summary(trials[-1]["point"])}', flush=True)
        best = min(trials, key=lambda t: t['score'])
        report['families'][kind] = {'trials': trials, 'selected': best['settings'], 'score': best['score'],
                                    'artifacts': best['artifacts']}
    write_json(output / 'run.json', report)
    print('Saved', output / 'run.json', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--check', action='store_true', help='two epochs of one setting per family, to test the setup')
    args = parser.parse_args()
    if args.check:
        run(args.output, args.device, epochs=2, limit=1)
    else:
        run(args.output, args.device)


if __name__ == '__main__':
    main()
