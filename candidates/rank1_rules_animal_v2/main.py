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
_SWITCH_PENALTY = max(0.0, float(_CONFIG.pop("switch_penalty", 0.0)))
_REACTIVE_RESCUE = str(_CONFIG.pop("reactive_rescue", "off"))
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
    previous = state.get("route")
    if previous is not None and distances[int(previous)] <= distances[route] + _SWITCH_PENALTY:
        route = int(previous)
    state["route"] = route
    return route


_AGENT = chassis.make_agent(_ROUTES, router=_router, **_CONFIG)
_RESCUE_STATS = {"changed": 0, "water": 0, "feed": 0, "collect": 0, "harvest": 0, "care": 0}


def _rescue_command(command, tile, inventory, day):
    if not isinstance(tile, dict): return None
    animal = tile.get("animal")
    if animal and _REACTIVE_RESCUE in ("strict", "broad", "animal", "feed_collect"):
        if not tile.get("fed_today") and int(inventory.get("WHEAT", 0)) > 0:
            return ["FEED"]
        if tile.get("fertilizer_available"):
            return ["COLLECT_FERTILIZER"]
        if _REACTIVE_RESCUE != "feed_collect" and int(tile.get("yield_units", 0)) > 0:
            return ["HARVEST"]
        if _REACTIVE_RESCUE == "broad" and not tile.get("cared_today"):
            return ["CARE"]
    if tile.get("kind") == "PLANT" and _REACTIVE_RESCUE in ("strict", "broad", "plant", "water"):
        if not tile.get("watered_today"):
            return ["WATER"]
        if _REACTIVE_RESCUE != "water" and int(tile.get("yield_units", 0)) > 0:
            crop = str(tile.get("crop", "")); first = {"WHEAT":2,"CARROT":2,"TOMATO":8,"STRAWBERRY":10,"MELON":10}.get(crop,0)
            if day - int(tile.get("planted_day", day)) >= first:return ["HARVEST"]
    return None


def _repair_certain_noops(action, observation):
    if _REACTIVE_RESCUE == "off": return action
    player = int(observation.get("player", 0)); farm = observation["farms"][player]
    private = observation.get("private", {}) or {}; seeds = private.get("seeds", {}) or {}; inventories = private.get("inventories", []) or []
    positions = [farm.get("farmer", [4,4]), *(farm.get("hands", []) or [])]
    commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
    while len(commands) < len(positions): commands.append(["PASS"])
    changed = False
    for index, position in enumerate(positions):
        command = commands[index]
        if not command or command[0] == "PASS": continue
        tile = chassis._tile_at(farm["tiles"], position); inventory = inventories[index] if index < len(inventories) else {}
        if not chassis._is_noop(command, tile, inventory, seeds, position, len(farm["tiles"])): continue
        replacement = _rescue_command(command, tile, inventory, int(observation.get("day", 0)))
        if replacement is None: continue
        commands[index] = replacement; changed = True
        key = replacement[0].lower().replace("_fertilizer", "")
        _RESCUE_STATS[key] = _RESCUE_STATS.get(key, 0) + 1
    if changed:
        _RESCUE_STATS["changed"] += 1
        action = dict(action); action["farmer"] = commands[0]; action["hands"] = commands[1:]
    return action


def agent(observation, configuration=None):
    try:
        return _repair_certain_noops(_AGENT(observation, configuration), observation)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}


agent.telemetry = {"chassis": _AGENT.chassis.diagnostics, "reactive_rescue": _RESCUE_STATS}
