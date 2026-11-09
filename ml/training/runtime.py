"""Explicit PyTorch device preflight; GPU requests never fall back silently."""
import importlib


def check_device(requested='cuda'):
    if requested not in {'cuda', 'cpu'}:
        raise ValueError('Choose cuda or cpu explicitly')
    try:
        torch = importlib.import_module('torch')
    except (ImportError, OSError) as error:
        raise RuntimeError('PyTorch is unavailable. Use the separate model environment and '
                           'ml/training/requirements-gpu-windows.txt; see docs/models/development.md.') from error
    if requested == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA was requested but PyTorch cannot use it. Check the CUDA wheel and NVIDIA driver; CPU fallback is disabled.')
    selected = 'cuda:0' if requested == 'cuda' else 'cpu'
    try:
        tensor = torch.ones((2, 2), device=selected)
        value = (tensor @ tensor).sum().item()
        if requested == 'cuda':
            torch.cuda.synchronize()
        if value != 8.:
            raise RuntimeError('Device tensor check returned an unexpected result')
        report = {'requested_device': requested, 'selected_device': selected, 'torch_version': torch.__version__,
                  'cuda_runtime': torch.version.cuda, 'tensor_check': 'passed', 'training_performed': False}
        if requested == 'cuda':
            properties = torch.cuda.get_device_properties(0)
            report.update({'gpu_name': properties.name, 'total_memory_mib': properties.total_memory / (1024 ** 2)})
        return report
    except (RuntimeError, OSError) as error:
        raise RuntimeError('Device preflight failed; no training started: ' + str(error)) from error
