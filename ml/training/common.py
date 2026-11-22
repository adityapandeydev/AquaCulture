"""Shared run setup, validation scoring and provenance."""
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ml.data.arrays import CarpRelease
from ml.data.files import digest
from ml.evaluation.metrics import point_metrics, quantile_metrics, relative_score
from ml.models.naive import fit_profile, naive_forecasts

CRITERIA = Path('docs/models/criteria.json')
DESCRIPTOR = Path('docs/data/carp-release.json')


class Development:
    """Fitting and validation data with their naive references."""

    def __init__(self):
        self.criteria = json.loads(CRITERIA.read_text(encoding='utf-8'))
        self.quantiles = tuple(self.criteria['quantiles'])
        self.release = CarpRelease(DESCRIPTOR)
        self.fit = self.release.samples('fit')
        self.sets = {name: self.release.samples(name) for name in self.criteria['selection']['sets']}
        self.profile = fit_profile(self.fit)
        self.naive = {}
        for name, samples in self.sets.items():
            forecasts = naive_forecasts(samples, self.profile)
            self.naive[name] = {k: [r['mae'] for r in point_metrics(samples, f)] for k, f in forecasts.items()}

    def score(self, forecasts):
        """Score {set: [n, 4, q]} quantile forecasts by the registered selection rule."""
        middle = self.quantiles.index(0.5)
        points = {s: point_metrics(self.sets[s], f[:, :, middle]) for s, f in forecasts.items()}
        maes = {s: [r['mae'] for r in rows] for s, rows in points.items()}
        return relative_score(maes, self.naive), points

    def details(self, forecasts):
        score, points = self.score(forecasts)
        intervals = {s: quantile_metrics(self.sets[s], f, self.quantiles) for s, f in forecasts.items()}
        return {'score': score, 'point': points, 'quantile': intervals}


def provenance():
    def git(*arguments):
        return subprocess.run(['git', *arguments], capture_output=True, text=True).stdout.strip()
    packages = {}
    for name in ['numpy', 'pandas', 'scikit-learn', 'torch']:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'git_revision': git('rev-parse', 'HEAD'),
            'uncommitted_ml': git('status', '--short', '--', 'ml', 'docs/models', 'docs/data').splitlines(),
            'source_sha256': {p.as_posix(): digest(p) for p in sorted(Path('ml').rglob('*.py')) if 'runs' not in p.parts},
            'criteria_sha256': digest(CRITERIA), 'release_descriptor_sha256': digest(DESCRIPTOR),
            'python': platform.python_version(), 'platform': platform.platform(), 'packages': packages}


def write_json(path, value):
    """Write completely before replacing, so an interrupted run leaves no partial record."""
    temporary = Path(str(path) + '.part')
    temporary.write_bytes((json.dumps(value, indent=1, allow_nan=False, default=float) + '
').encode())
    temporary.replace(path)


def summary(points):
    return ' | '.join(f"{name.replace('validation_', '').replace('_pond', '')} "
                      + ' '.join(f"+{r['horizon']}h {r['mae']:.3f}" for r in rows) for name, rows in points.items())
