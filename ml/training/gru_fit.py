"""One bounded stochastic fit; the experiment runner handles cases and seed selection."""
import json
import importlib
import os
import random
import time

import numpy as np


def prepare_randomness(seed, device):
    # Set before the first CUDA operation, including preflight in the experiment runner.
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    if os.environ['CUBLAS_WORKSPACE_CONFIG'] not in {':4096:8', ':16:8'}:
        raise ValueError('Use a deterministic CUBLAS_WORKSPACE_CONFIG (:4096:8 or :16:8)')
    try:
        torch = importlib.import_module('torch')
    except (ImportError, OSError) as error:
        raise RuntimeError('PyTorch is unavailable; install the separate model environment described in docs/models/development.md') from error
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device.startswith('cuda'):
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


def fit_replica(train, validation, setting, settings, seed, device, output, maximum_seconds, parameter_cap, emit):
    import torch
    from ml.modeling.gru import DOForecaster, fit_channel_scaling, load_checkpoint
    prepare_randomness(seed, device)
    started = time.perf_counter()
    output.mkdir(parents=True)
    mean, scale = fit_channel_scaling(train.x)
    model = DOForecaster(train.x.shape[-1], setting['hidden_size'], mean, scale).to(device)
    parameters = sum(p.numel() for p in model.parameters())
    if parameters > parameter_cap:
        raise ValueError('Model exceeds the registered parameter budget')
    optimizer = torch.optim.AdamW(model.parameters(), lr=setting['learning_rate'], weight_decay=settings['weight_decay'])
    tx, ty, vx = [torch.as_tensor(a, dtype=torch.float32, device=device) for a in [train.x, train.y, validation.x]]
    generator = torch.Generator(device='cpu').manual_seed(seed)
    best, best_epoch, stale, history = float('inf'), None, 0, []
    if device.startswith('cuda'):
        torch.cuda.reset_peak_memory_stats()
    for epoch in range(1, settings['maximum_epochs'] + 1):
        if time.perf_counter() - started > maximum_seconds:
            raise TimeoutError('Registered per-fit wall budget exceeded; candidate is ineligible')
        model.train()
        order = torch.randperm(len(tx), generator=generator)
        for offset in range(0, len(tx), settings['batch_size']):
            indices = order[offset:offset + settings['batch_size']].to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = (((model(tx[indices]) - ty[indices]) / model.scale[0]) ** 2).mean()
            if not torch.isfinite(loss):
                raise ValueError('Non-finite training loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), settings['gradient_clip_norm'], error_if_nonfinite=True)
            optimizer.step()
        model.eval()
        with torch.inference_mode():
            train_values = model(tx).cpu().numpy().astype(np.float64)
            values = model(vx).cpu().numpy().astype(np.float64)
        train_mae = float(np.abs(train_values - train.y).mean())
        if not np.isfinite(train_mae):
            raise ValueError('Non-finite training predictions')
        valid = bool(np.isfinite(values).all() and (values >= 0).all())
        mae = float(np.abs(values - validation.y).mean()) if valid else None
        improved = valid and mae < best
        if improved:
            best, best_epoch, stale = mae, epoch, 0
            record = {'version': 'compact-do-gru-v1', 'history_hours': 6, 'features': train.x.shape[-1],
                      'hidden_size': setting['hidden_size'], 'seed': seed, 'epoch': epoch,
                      'state_dict': {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}}
            temporary = output / 'best.tmp'
            torch.save(record, temporary)
            temporary.replace(output / 'best.pt')
        else:
            stale += 1
        elapsed = time.perf_counter() - started
        row = {'epoch': epoch, 'train_mae_mgL': train_mae, 'validation_mae_mgL': mae,
               'complete_validation_predictions': valid, 'checkpoint_improved': improved, 'elapsed_seconds': elapsed}
        history.append(row)
        with (output / 'epochs.jsonl').open('a', encoding='utf-8') as log:
            log.write(json.dumps(row, allow_nan=False) + '\n')
        emit(f'    seed={seed} epoch={epoch}/{settings["maximum_epochs"]} train_MAE={train_mae:.6f} '
             f'validation_MAE={mae} elapsed={elapsed:.1f}s' + (' checkpoint saved' if improved else ''))
        if elapsed > maximum_seconds:
            raise TimeoutError('Registered per-fit wall budget exceeded; candidate is ineligible')
        if stale >= settings['patience']:
            break
    if best_epoch is None:
        raise ValueError('No complete finite validation checkpoint')
    restored, _ = load_checkpoint(output / 'best.pt', device)
    with torch.inference_mode():
        forecasts = {name: restored(x).cpu().numpy().astype(np.float64) for name, x in [('train', tx), ('validation', vx)]}
    if time.perf_counter() - started > maximum_seconds:
        raise TimeoutError('Registered per-fit wall budget exceeded during checkpoint restoration')
    return {'seed': seed, 'best_epoch': best_epoch, 'epochs_completed': len(history), 'parameter_count': parameters,
            'fit_seconds': time.perf_counter() - started, 'best_validation_mae_mgL': best,
            'stopping_reason': 'validation_patience' if stale >= settings['patience'] else 'maximum_epochs',
            'peak_cuda_allocated_bytes': torch.cuda.max_memory_allocated() if device.startswith('cuda') else None}, forecasts
