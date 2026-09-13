"""Pure-NumPy hierarchical policy cloned from Majkel1337 public replays."""

from __future__ import annotations

import json
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


def agent(observation):
    weights = _load()
    state, actors, valid = encode_observation(observation)
    shared = _gelu(_layer_norm(_linear(state, "state.0", weights), "state.1", weights))
    shared = _gelu(_layer_norm(_linear(shared, "state.3", weights), "state.4", weights))
    actor_embedding = _gelu(_linear(actors, "actor.0", weights))
    actor_input = np.concatenate((np.broadcast_to(shared, (MAX_ACTORS, len(shared))), actor_embedding), axis=-1)
    actor_hidden = _gelu(_linear(actor_input, "actor_head.0", weights))
    actor_ids = _linear(actor_hidden, "actor_head.2", weights).argmax(axis=-1)
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
        "market": market,
    }
