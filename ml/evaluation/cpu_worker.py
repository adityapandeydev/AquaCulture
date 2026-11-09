"""Fresh-process benchmark worker. Heavy runtime imports occur after baseline RSS."""
import argparse
import ctypes
import importlib.metadata
import json
import os
import platform
import sys
import time
from pathlib import Path


def cpu_name():
    if sys.platform == 'win32':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            return winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    if sys.platform.startswith('linux'):
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                return line.split(':', 1)[1].strip()
    return platform.processor()


def process_memory():
    if sys.platform == 'win32':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ['PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage',
                 'PeakPagefileUsage', 'PrivateUsage']]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        api = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
        api.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        api.restype = wintypes.BOOL
        record = Counters()
        record.cb = ctypes.sizeof(record)
        if not api(kernel.GetCurrentProcess(), ctypes.byref(record), record.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'rss_bytes': record.WorkingSetSize, 'peak_rss_bytes': record.PeakWorkingSetSize}
    if sys.platform.startswith('linux'):
        import resource
        rss = int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
        return {'rss_bytes': rss, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    raise RuntimeError('Peak/current RSS measurement is implemented for Windows and Linux only')


def measure(payload_path, phase, warmups=20, repetitions=100):
    baseline = process_memory()
    started = time.perf_counter()
    import numpy as np
    from ml.modeling.cpu import CPUForecast, assemble_history
    payload = json.loads(Path(payload_path).read_text(encoding='utf-8'))
    predictor = CPUForecast(payload['family'], payload['artifact'], payload['features'])
    first = predictor.from_history(payload['histories'][0])
    first_seconds = time.perf_counter() - started
    expected = np.asarray(payload['expected_predictions'], dtype=np.float64)
    if not np.allclose(first, expected[:1], rtol=1e-6, atol=1e-5):
        raise ValueError('First CPU prediction differs from the bound development forecast')
    result = {'phase': phase, 'baseline_memory': baseline, 'import_load_first_prediction_seconds': first_seconds,
              'parameter_count': int(predictor.parameters), 'python': platform.python_version(),
              'numpy': np.__version__, 'cpu_name': cpu_name(),
              'platform': platform.platform(), 'logical_cpus': os.cpu_count(), 'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES'),
              'thread_environment': {k: os.environ.get(k) for k in ['OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS']}}
    if payload['family'] == 'gru':
        import torch
        result.update({'torch': torch.__version__, 'torch_threads': torch.get_num_threads(),
                       'torch_interop_threads': torch.get_num_interop_threads(), 'model_device': str(next(predictor.model.parameters()).device)})
    if phase == 'warm':
        if warmups < 20 or repetitions < 100:
            raise ValueError('Use at least 20 warmups and 100 measured predictions')
        arrays = [assemble_history(h, tuple(payload['features'])) for h in payload['histories']]
        prepared = [predictor.prepare(a) for a in arrays]
        values = np.concatenate([predictor.predict(a) for a in prepared])
        if not np.isfinite(values).all() or not np.allclose(values, expected, rtol=1e-6, atol=1e-5):
            raise ValueError('CPU predictions differ from bound development forecasts')
        def model_only(index):
            return predictor.predict(prepared[index % len(prepared)])
        def preprocessing_and_model(index):
            return predictor.from_history(payload['histories'][index % len(arrays)])
        timings = {}
        for name, function in [('model_only', model_only), ('hourly_history_preprocessing_plus_model', preprocessing_and_model)]:
            for index in range(warmups):
                function(index)
            samples = []
            for index in range(repetitions):
                before = time.perf_counter_ns()
                function(index)
                samples.append((time.perf_counter_ns() - before) / 1e6)
            timings[name] = {'median_ms': float(np.median(samples)), 'p95_ms': float(np.quantile(samples, .95)),
                             'samples_ms': samples}
        batch = predictor.prepare(np.concatenate([arrays[i % len(arrays)] for i in range(32)]))
        for _ in range(warmups):
            predictor.predict(batch)
        before = time.perf_counter()
        for _ in range(repetitions):
            predictor.predict(batch)
        elapsed = time.perf_counter() - before
        result.update({'timings': timings, 'batch32_windows_per_second': 32 * repetitions / elapsed,
                       'batch32_total_seconds': elapsed, 'batch32_repetitions': repetitions,
                       'warmups': warmups, 'single_window_repetitions': repetitions, 'prediction_parity': 'passed',
                       'distinct_validation_windows': len(arrays)})
    result['memory'] = process_memory()
    result['environment_packages'] = dict(sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', required=True, type=Path)
    parser.add_argument('--phase', choices=['cold', 'warm'], required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.payload, args.phase), allow_nan=False))


if __name__ == '__main__':
    main()
