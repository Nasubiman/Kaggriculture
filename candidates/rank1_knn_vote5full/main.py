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
_SWITCH_INTERVAL = max(1, int(_CONFIG.pop("switch_interval", 1)))
_REWARD_BONUS = float(_CONFIG.pop("reward_bonus", 0.0))
_VOTE_K = max(1, int(_CONFIG.pop("vote_k", 1)))
_VOTE_SCOPE = str(_CONFIG.pop("vote_scope", "units"))
rank1_knn._load()
_ROUTES = {index: tape for index, tape in enumerate(rank1_knn._TAPES)}
_DISTANCE_TRACE = []
_REWARDS = None
if _REWARD_BONUS:
    _metadata = json.loads((_ROOT / "metadata.json").read_text())
    _REWARDS = np.asarray([row["reward"] for row in _metadata["episodes"]], dtype=np.float64)
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
    if state.get("route") is not None and step % _SWITCH_INTERVAL:
        return int(state["route"])
    current = rank1_knn.encode(observation)
    library = rank1_knn._FEATURES[step]
    mismatch = (library[:, :100] != current[:100]).sum(axis=1, dtype=np.int32) * int(_DISTANCE.get("tile", 30))
    differences = np.abs(
        library[:, 100:].astype(np.int16) - current[None, 100:]
    ).astype(np.int32)
    distances = mismatch + (
        differences * _MATCH_WEIGHTS[100:]
    ).sum(axis=1, dtype=np.int32)
    if _REWARDS is not None:
        distances = distances.astype(np.float64) - (_REWARDS - np.median(_REWARDS)) * (_REWARD_BONUS / 1000.0)
    if _SAME_SEAT:
        distances[library[:, -1] != current[-1]] = 1_000_000_000
    _DISTANCE_TRACE.append((int(step), int(distances.min())))
    order = np.argsort(distances)[:_VOTE_K]
    route = int(order[0])
    if _VOTE_K > 1:
        counts = {}
        keys = []
        for neighbor in order:
            action = _ROUTES[int(neighbor)][step]
            value = action if _VOTE_SCOPE == "full" else {
                "farmer": action.get("farmer"), "hands": action.get("hands", [])
            }
            key = json.dumps(value, sort_keys=True, separators=(",", ":"))
            keys.append(key); counts[key] = counts.get(key, 0) + 1
        best = max(counts, key=lambda key: counts[key])
        route = int(order[keys.index(best)])
    state["route"] = route
    return route


_AGENT = chassis.make_agent(_ROUTES, router=_router, **_CONFIG)


def agent(observation, configuration=None):
    try:
        return _AGENT(observation, configuration)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}


agent.telemetry = _AGENT.chassis.diagnostics
