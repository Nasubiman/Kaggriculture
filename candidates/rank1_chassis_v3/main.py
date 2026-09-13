"""Run nearest rank-1 trajectories through the proven route-replay chassis."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import chassis
import rank1_knn


_CONFIG = json.loads((_ROOT / "settings.json").read_text())
rank1_knn._load()
_ROUTES = {index: tape for index, tape in enumerate(rank1_knn._TAPES)}


def _router(observation, step, state):
    current = rank1_knn.encode(observation)
    library = rank1_knn._FEATURES[step]
    mismatch = (library[:, :100] != current[:100]).sum(axis=1, dtype=np.int32) * 30
    differences = np.abs(
        library[:, 100:].astype(np.int16) - current[None, 100:]
    ).astype(np.int32)
    distances = mismatch + (
        differences * rank1_knn._WEIGHTS[100:]
    ).sum(axis=1, dtype=np.int32)
    distances[library[:, -1] != current[-1]] = 1_000_000_000
    return int(distances.argmin())


_AGENT = chassis.make_agent(_ROUTES, router=_router, **_CONFIG)


def agent(observation, configuration=None):
    try:
        return _AGENT(observation, configuration)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}


agent.telemetry = _AGENT.chassis.diagnostics
