"""Write a raw sensor CSV and reference forecasts for the backend's whole-system test."""
import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ml.models.blend import blend, load_families
from ml.training.common import Development

from .conformal import apply_offsets
from .final import CANDIDATE
from .metrics import probability_below

SOURCE = Path('Datasets/external/fwi_campaign_2026/csv')


def run(output, count):
    """Use one unseen validation pond. Reserved partitions stay closed."""
    candidate = json.loads(CANDIDATE.read_text(encoding='utf-8'))
    data, models = Development(), load_families(candidate['artifacts'])
    samples = data.sets['validation_unseen_pond']
    pond = 'ara2_4f79fc8d'
    rows = np.flatnonzero((samples.pond == pond) & (np.isfinite(samples.x).sum(axis=1).min(axis=1) == 24))
    rows = rows[np.linspace(0, len(rows) - 1, min(count, len(rows))).astype(int)]
    forecast = apply_offsets(blend({f: m.predict(samples) for f, m in models.items()}, candidate['weights']), data.quantiles,
                             candidate['pairs'], candidate['candidates']['blend']['offsets_by_horizon_and_pair'])
    probability = probability_below(forecast, data.quantiles, data.criteria['alert_gates']['gated_threshold_mgL'])
    middle, low, high = (data.quantiles.index(q) for q in (0.5, 0.05, 0.95))
    cases = []
    for i in rows:
        issue = pd.Timestamp(samples.issue[i]).tz_localize('Asia/Kolkata') + timedelta(hours=1)
        cases.append({'issue': issue.isoformat(), 'point': forecast[i, :, middle].tolist(), 'low': float(forecast[i, 0, low]),
                      'high': float(forecast[i, 0, high]), 'probabilities': probability[i].tolist()})
    raw = pd.read_csv(SOURCE / f'{pond}.csv').iloc[:, :4]
    raw.columns = ['timestamp', 'do_mgl', 'ph', 'temperature_c']
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'pond': pond, 'csv': raw.to_csv(index=False, lineterminator='\n'), 'cases': cases}), encoding='utf-8')
    print(f'{len(cases)} reference forecasts for {pond} in {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('ml/runs/chain-reference.json'))
    parser.add_argument('--count', type=int, default=150)
    args = parser.parse_args()
    run(args.output, args.count)


if __name__ == '__main__':
    main()
