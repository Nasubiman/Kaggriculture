"""Fourth Quadrant replay imitation with deterministic local task repair.

The replay library supplies movement, purchasing and spatial assignments.
Only tasks that are immediately useful on an actor's current tile are
recomputed from the live observation. This is a research multi-file agent.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import rank1_knn


def _local_task(tile, inventory, mode):
    if not isinstance(tile, dict):
        return None
    kind = tile.get("kind")
    animal = tile.get("animal")
    if animal:
        if not tile.get("fed_today") and int(inventory.get("WHEAT", 0)) > 0:
            return ["FEED"]
        if tile.get("fertilizer_available"):
            return ["COLLECT_FERTILIZER"]
        if int(tile.get("yield_units", 0)) > 0:
            return ["HARVEST"]
        if mode == "full" and not tile.get("cared_today"):
            return ["CARE"]
    elif kind == "PLANT":
        if not tile.get("watered_today"):
            return ["WATER"]
        if mode == "full" and int(tile.get("yield_units", 0)) > 0:
            return ["HARVEST"]
    return None


def agent(observation, configuration=None):
    action = rank1_knn.agent(observation, configuration)
    player = int(observation["player"])
    farm = observation["farms"][player]
    positions = [farm["farmer"], *(farm.get("hands") or [])]
    inventories = (observation.get("private") or {}).get("inventories") or []
    commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
    if len(commands) < len(positions):
        commands.extend([["PASS"] for _ in range(len(positions) - len(commands))])
    mode = "full"
    for index, (x, y) in enumerate(positions):
        if not 0 <= x < 10 or not 0 <= y < 10:
            continue
        inventory = inventories[index] if index < len(inventories) else {}
        replacement = _local_task(farm["tiles"][y][x], inventory, mode)
        if replacement is not None:
            commands[index] = replacement
    return dict(action, farmer=commands[0], hands=commands[1:])
