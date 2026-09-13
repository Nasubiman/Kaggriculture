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
_SAME_SEAT = bool(_CONFIG.pop("same_seat", False))
_DISTANCE = _CONFIG.pop("distance", {})
rank1_knn._load()
_ROUTES = {index: tape for index, tape in enumerate(rank1_knn._TAPES)}
_MATCH_WEIGHTS = rank1_knn._WEIGHTS.copy()
for _name, (_start, _end) in {
    "yield": (100, 200), "flags": (200, 300), "neglect": (300, 400),
    "age": (400, 500), "positions": (500, 532), "carried": (532, 676),
    "own_macro": (676, 693), "market": (693, 711), "shops": (711, 719),
    "opponent": (719, 734),
}.items():
    _MATCH_WEIGHTS[_start:_end] = np.maximum(
        0, np.rint(_MATCH_WEIGHTS[_start:_end] * float(_DISTANCE.get(_name, 1.0)))
    ).astype(np.int32)


def _router(observation, step, state):
    current = rank1_knn.encode(observation)
    library = rank1_knn._FEATURES[step]
    mismatch = (library[:, :100] != current[:100]).sum(axis=1, dtype=np.int32) * int(_DISTANCE.get("tile", 30))
    differences = np.abs(
        library[:, 100:].astype(np.int16) - current[None, 100:]
    ).astype(np.int32)
    distances = mismatch + (
        differences * _MATCH_WEIGHTS[100:]
    ).sum(axis=1, dtype=np.int32)
    if _SAME_SEAT:
        distances[library[:, -1] != current[-1]] = 1_000_000_000
    return int(distances.argmin())


_AGENT = chassis.make_agent(_ROUTES, router=_router, **_CONFIG)


def agent(observation, configuration=None):
    try:
        return _AGENT(observation, configuration)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}


agent.telemetry = _AGENT.chassis.diagnostics
