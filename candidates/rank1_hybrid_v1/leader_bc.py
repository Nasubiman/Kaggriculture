"""Pure-NumPy hierarchical policy cloned from Majkel1337 public replays."""

from __future__ import annotations

import json
import copy
from pathlib import Path
import sys

import numpy as np

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from rank1_bc_model import MAX_ACTORS, MAX_MARKET_ORDERS, encode_observation


_WEIGHTS = None
_ACTOR_VOCAB = None
_MARKET_VOCAB = None

# These first 21 actions are identical in all 235 current rank-1 public games.
# Freezing them removes the most damaging behavior-cloning covariate shift.
_OPENING = [
 {"farmer":["PASS"],"hands":[],"market":[["BUY_ANIMAL","COW",1],["BUY_PRODUCT","WHEAT",5]]},
 {"farmer":["PICKUP","COW",1],"hands":[],"market":[["SELL","WHEAT",1],["HIRE"],["HIRE"],["HIRE"],["HIRE"],["BUY_ANIMAL","COW",1],["BUY_ANIMAL","SHEEP",3]]},
 {"farmer":["BUILD_PASTURE"],"hands":[["PICKUP","SHEEP",1],["PICKUP","SHEEP",1],["PICKUP","COW",1],["PICKUP","SHEEP",1]],"market":[["SELL","WHEAT",1]]},
 {"farmer":["PLACE","COW",1],"hands":[["NORTH"],["NORTH"],["NORTH"],["WEST"]],"market":[["SELL","WHEAT",1],["BUY_PRODUCT","WHEAT",1]]},
 {"farmer":["PICKUP","WHEAT",3],"hands":[["WEST"],["WEST"],["NORTH"],["BUILD_PASTURE"]],"market":[["SELL","WHEAT",1],["BUY_PRODUCT","WHEAT",1]]},
 {"farmer":["FEED"],"hands":[["BUILD_PASTURE"],["WEST"],["NORTH"],["PLACE","SHEEP",1]],"market":[["SELL","WHEAT",1],["BUY_PRODUCT","WHEAT",1]]},
 {"farmer":["WEST"],"hands":[["PLACE","SHEEP",1],["BUILD_PASTURE"],["WEST"],["CARE"]],"market":[["BUY_SEED","MELON",2],["BUY_PRODUCT","WHEAT",1]]},
 {"farmer":["FEED"],"hands":[["CARE"],["PLACE","SHEEP",1],["BUILD_PASTURE"],["WEST"]],"market":[]},
 {"farmer":["WEST"],"hands":[["SOUTH"],["WEST"],["PLACE","COW",1],["WEST"]],"market":[["BUY_SEED","MELON",2]]},
 {"farmer":["FEED"],"hands":[["PICKUP","WHEAT",1],["NORTH"],["NORTH"],["NORTH"]],"market":[]},
 {"farmer":["CARE"],"hands":[["NORTH"],["PLANT","MELON"],["PLANT","MELON"],["PLANT","MELON"]],"market":[]},
 {"farmer":["WEST"],"hands":[["FEED"],["WATER"],["WATER"],["WATER"]],"market":[["BUY_SEED","MELON",2]]},
 {"farmer":["PLANT","MELON"],"hands":[["NORTH"],["NORTH"],["WEST"],["NORTH"]],"market":[]},
 {"farmer":["WATER"],"hands":[["WEST"],["PLANT","MELON"],["PLANT","MELON"],["PLANT","MELON"]],"market":[["BUY_SEED","WHEAT",2]]},
 {"farmer":["WEST"],"hands":[["PLANT","MELON"],["WATER"],["WATER"],["WATER"]],"market":[["BUY_SEED","WHEAT",1]]},
 {"farmer":["PLANT","WHEAT"],"hands":[["WATER"],["NORTH"],["WEST"],["NORTH"]],"market":[["BUY_SEED","WHEAT",1]]},
 {"farmer":["WATER"],"hands":[["WEST"],["PLANT","WHEAT"],["PLANT","WHEAT"],["PLANT","WHEAT"]],"market":[["BUY_SEED","WHEAT",1]]},
 {"farmer":["NORTH"],"hands":[["PLANT","WHEAT"],["WATER"],["WATER"],["WATER"]],"market":[["SELL","WHEAT",1],["BUY_SEED","WHEAT",1]]},
 {"farmer":["PLANT","WHEAT"],"hands":[["WATER"],["NORTH"],["NORTH"],["WEST"]],"market":[["BUY_SEED","WHEAT",1]]},
 {"farmer":["WATER"],"hands":[["WEST"],["SOUTH"],["PLANT","WHEAT"],["PLANT","WHEAT"]],"market":[["BUY_SEED","WHEAT",1]]},
 {"farmer":["NORTH"],"hands":[["WEST"],["WEST"],["WATER"],["WATER"]],"market":[["BUY_SEED","WHEAT",1]]},
]


def _load():
    global _WEIGHTS, _ACTOR_VOCAB, _MARKET_VOCAB
    if _WEIGHTS is None:
        _WEIGHTS = np.load(_ROOT / "model_weights.npz")
        vocab = json.loads((_ROOT / "vocab.json").read_text())
        _ACTOR_VOCAB = [json.loads(value) for value in vocab["actor_vocab"]]
        _MARKET_VOCAB = [None, *(json.loads(value) for value in vocab["market_vocab"][1:])]
    return _WEIGHTS


def _linear(x, prefix, weights):
    return x @ weights[prefix + ".weight"].T + weights[prefix + ".bias"]


def _layer_norm(x, prefix, weights):
    mean = x.mean(axis=-1, keepdims=True)
    variance = ((x - mean) ** 2).mean(axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(variance + 1e-5) * weights[prefix + ".weight"] + weights[prefix + ".bias"]


def _gelu(x):
    # Fast approximation is sufficiently close to torch's exact GELU for argmax inference.
    return .5 * x * (1.0 + np.tanh(.7978845608 * (x + .044715 * x * x * x)))


def _near_shed(x, y):
    return (x, y) in {(4, 4), (5, 4), (4, 5), (5, 5)}


def _legal(command, observation, actor_index):
    op = command[0]
    if op == "PASS": return True
    seat = int(observation.get("player", 0)); farm = observation["farms"][seat]
    positions = [farm.get("farmer", [4, 4]), *(farm.get("hands", []) or [])]
    if actor_index >= len(positions): return False
    x, y = map(int, positions[actor_index]); tile = farm["tiles"][y][x]
    private = observation.get("private", {}) or {}; inventories = private.get("inventories", []) or []
    inventory = inventories[actor_index] if actor_index < len(inventories) else {}
    if op == "NORTH": return y > 0
    if op == "SOUTH": return y < 9
    if op == "WEST": return x > 0
    if op == "EAST": return x < 9
    if op == "PICKUP": return _near_shed(x, y) and private.get("shed", {}).get(command[1], 0) > 0
    if op == "DROP": return _near_shed(x, y) and bool(inventory)
    if op == "PLACE":
        item = command[1]
        if item in ("COW", "SHEEP", "GOOSE"):
            structure = "COOP" if item == "GOOSE" else "PASTURE"
            return (isinstance(tile, dict) and tile.get("kind") == structure and
                    not tile.get("animal") and inventory.get(item, 0) > 0)
        return _near_shed(x, y) and inventory.get(item, 0) > 0
    if op == "PLANT": return tile is None and private.get("seeds", {}).get(command[1], 0) > 0
    if op == "WATER": return isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile.get("watered_today")
    if op == "HARVEST":
        if not isinstance(tile, dict) or tile.get("yield_units", 0) <= 0: return False
        first = {"WHEAT":2,"CARROT":2,"TOMATO":8,"STRAWBERRY":10,"MELON":10}
        return tile.get("kind") != "PLANT" or int(observation.get("day", 0))-int(tile.get("planted_day", 0)) >= first.get(tile.get("crop"), 0)
    if op == "FERTILIZE": return isinstance(tile, dict) and tile.get("kind") == "PLANT" and inventory.get("FERTILIZER", 0) > 0
    if op == "DIG": return tile is not None and not (isinstance(tile, dict) and tile.get("animal"))
    if op in ("BUILD_PASTURE", "BUILD_COOP"): return tile is None
    if op == "FEED": return isinstance(tile, dict) and tile.get("animal") and not tile.get("fed_today") and inventory.get("WHEAT", 0) > 0
    if op == "CARE": return isinstance(tile, dict) and tile.get("animal") and not tile.get("cared_today")
    if op == "COLLECT_FERTILIZER": return isinstance(tile, dict) and tile.get("animal") and bool(tile.get("fertilizer_available"))
    return False


def _filter_market(commands, observation):
    day = int(observation.get("day", 0)); seat = int(observation.get("player", 0))
    farm = observation["farms"][seat]; current_hands = len(farm.get("hands", []) or [])
    targets = (4, 5, 6, 6, 6, 6, 8, 9, 9, 10, *([11] * 18), 10, 10)
    target = targets[min(day, len(targets)-1)]; hires = 0
    remaining = dict((observation.get("private", {}) or {}).get("shed", {}) or {})
    result = []
    for command in commands:
        if command[0] == "HIRE":
            if current_hands + hires >= target: continue
            hires += 1
        elif command[0] == "SELL" and len(command) >= 3:
            item, quantity = command[1], int(command[2]); available = int(remaining.get(item, 0))
            if available <= 0: continue
            quantity = min(quantity, available); remaining[item] = available - quantity
            command = ["SELL", item, quantity]
        result.append(command)
        if len(result) >= MAX_MARKET_ORDERS: break
    return result


def agent(observation):
    step = int(observation.get("step", int(observation.get("day", 0))*24 + int(observation.get("hour", 0))))
    if step < len(_OPENING):
        return copy.deepcopy(_OPENING[step])
    weights = _load()
    state, actors, valid = encode_observation(observation)
    shared = _gelu(_layer_norm(_linear(state, "state.0", weights), "state.1", weights))
    shared = _gelu(_layer_norm(_linear(shared, "state.3", weights), "state.4", weights))
    actor_embedding = _gelu(_linear(actors, "actor.0", weights))
    actor_input = np.concatenate((np.broadcast_to(shared, (MAX_ACTORS, len(shared))), actor_embedding), axis=-1)
    actor_hidden = _gelu(_linear(actor_input, "actor_head.0", weights))
    actor_logits = _linear(actor_hidden, "actor_head.2", weights)
    for actor_index in range(int(valid.sum())):
        legal = np.fromiter((_legal(command, observation, actor_index) for command in _ACTOR_VOCAB),
                            dtype=np.bool_, count=len(_ACTOR_VOCAB))
        actor_logits[actor_index, ~legal] = -1e30
    actor_ids = actor_logits.argmax(axis=-1)
    market_hidden = _gelu(_linear(shared, "market_head.0", weights))
    market_logits = _linear(market_hidden, "market_head.2", weights).reshape(MAX_MARKET_ORDERS, -1)
    market_ids = market_logits.argmax(axis=-1)
    commands = [_ACTOR_VOCAB[int(actor_ids[index])] for index in range(int(valid.sum()))]
    market = []
    for value in market_ids:
        command = _MARKET_VOCAB[int(value)]
        if command is None:
            break
        market.append(command)
    return {
        "farmer": commands[0] if commands else ["PASS"],
        "hands": commands[1:],
        "market": _filter_market(market, observation),
    }
