"""Measure startup, latency and memory of the real service in a separate process."""
import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import numpy as np
import psutil

LIMITS = Path('docs/models/criteria.json')
ISSUE = datetime(2026, 1, 24, 6, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def example():
    history = [{'start': (ISSUE - timedelta(hours=k)).isoformat(), 'coverage': 1.0, 'do_mgL': 6 + 3 * float(np.sin(k / 24 * 6.28)),
                'ph': 8.4, 'temperature_c': 26.0} for k in range(24, 0, -1)]
    return {'species': 'rohu_catla', 'timezone': 'Asia/Kolkata', 'issue_time': ISSUE.isoformat(), 'history': history}


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def peak_memory(process):
    """Peak resident memory of the service process and any child, in MiB."""
    total = 0
    for p in [process, *process.children(recursive=True)]:
        info = p.memory_info()
        total += getattr(info, 'peak_wset', info.rss)
    return total / 2 ** 20


def timed(client, body, count):
    samples = []
    for _ in range(count):
        started = time.perf_counter()
        client.post('/v2/forecasts', json=body).raise_for_status()
        samples.append((time.perf_counter() - started) * 1000)
    return samples


def run(output, repetitions, workers):
    if output.exists():
        raise FileExistsError('Use a new benchmark file: ' + str(output))
    port, body = free_port(), example()
    environment = {**os.environ, 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}
    started = time.perf_counter()
    server = subprocess.Popen([sys.executable, '-B', '-m', 'ml.service.app', '--port', str(port)], env=environment,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30) as client:
            while True:
                try:
                    client.get('/ready').raise_for_status()
                    break
                except httpx.HTTPError:
                    if server.poll() is not None or time.perf_counter() - started > 60:
                        raise RuntimeError('The service did not become ready')
                    time.sleep(0.05)
            first = client.post('/v2/forecasts', json=body)
            first.raise_for_status()
            startup = time.perf_counter() - started
            timed(client, body, 20)
            single = timed(client, body, repetitions)

        parallel, errors = [], []

        def work():
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30) as own:
                    parallel.extend(timed(own, body, repetitions // workers))
            except Exception as error:
                errors.append(str(error))
        threads = [threading.Thread(target=work) for _ in range(workers)]
        begun = time.perf_counter()
        [t.start() for t in threads]
        [t.join() for t in threads]
        throughput = len(parallel) / (time.perf_counter() - begun)
        memory = peak_memory(psutil.Process(server.pid))
    finally:
        for child in psutil.Process(server.pid).children(recursive=True) if server.poll() is None else []:
            child.terminate()
        server.terminate()
        server.wait(10)

    limits = json.loads(LIMITS.read_text(encoding='utf-8'))['resource_limits']
    size = sum(f.stat().st_size for f in Path('ml/bundles/carp-1').iterdir()) / 2 ** 20
    p95 = float(np.quantile(single, 0.95))
    report = {'processor': platform.processor(), 'python': platform.python_version(), 'machine_load_percent': psutil.cpu_percent(1),
              'load_and_first_forecast_seconds': startup, 'single': {'requests': len(single), 'median_ms': float(np.median(single)), 'p95_ms': p95},
              'parallel': {'workers': workers, 'requests': len(parallel), 'p95_ms': float(np.quantile(parallel, 0.95)) if parallel else None,
                           'requests_per_second': throughput, 'errors': errors},
              'peak_memory_mib': memory, 'artifact_mib': size,
              'passed': {'latency': p95 <= limits['maximum_single_forecast_p95_ms'],
                         'startup': startup <= limits['maximum_load_and_first_forecast_seconds'],
                         'artifact': size <= limits['maximum_artifact_mib'], 'memory': memory <= limits['maximum_peak_rss_mib']}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(report, indent=1) + '\n').encode())
    print(json.dumps(report, indent=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=400)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    run(args.output, args.repetitions, args.workers)


if __name__ == '__main__':
    main()
