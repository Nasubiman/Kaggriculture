"""Runtime-only accelerators for trusted pure-Python competition agents."""

from __future__ import annotations

import copy as _copy
from types import ModuleType
from typing import Any


_ATOMIC = (type(None), bool, int, float, str, bytes)

try:
    import _kaggriculture_native as _native
except Exception:  # optional accelerator; Kaggle/submission path stays pure Python
    _native = None


def fast_deepcopy(value: Any, memo: dict[int, Any] | None = None) -> Any:
    """Fast deepcopy for exact JSON containers, stdlib fallback otherwise."""
    if type(value) in _ATOMIC:
        return value
    if memo is None:
        memo = {}
    identity = id(value)
    cached = memo.get(identity)
    if cached is not None:
        return cached
    kind = type(value)
    if kind is list:
        result: list[Any] = []
        memo[identity] = result
        append = result.append
        for item in value:
            append(fast_deepcopy(item, memo))
        return result
    if kind is dict:
        result_dict: dict[Any, Any] = {}
        memo[identity] = result_dict
        for key, item in value.items():
            result_dict[fast_deepcopy(key, memo)] = fast_deepcopy(item, memo)
        return result_dict
    if kind is tuple:
        result_tuple = tuple(fast_deepcopy(item, memo) for item in value)
        memo[identity] = result_tuple
        return result_tuple
    if kind is set:
        result_set: set[Any] = set()
        memo[identity] = result_set
        for item in value:
            result_set.add(fast_deepcopy(item, memo))
        return result_set
    return _copy.deepcopy(value, memo)


class _CopyProxy:
    deepcopy = staticmethod(fast_deepcopy)

    def __getattr__(self, name: str) -> Any:
        return getattr(_copy, name)


def _install_fast_gain(module: ModuleType) -> None:
    """Replace generator-heavy _r51_input_gain with an equivalent tight loop."""
    ns = module.__dict__
    original = ns.get("_r51_input_gain")
    if not callable(original) or getattr(original, "_runtime_accelerated", False):
        return

    def fast_gain(target, arrival, day):
        harvest = target["harvest"]
        if harvest is None or harvest <= arrival:
            return 0
        until = target["until"]
        extra = 0
        baseline = target["yield"]
        for t in target["water"]:
            tday = t // 24
            if arrival < t <= harvest and day <= tday <= day + 2 and tday > until:
                extra += 1
            baseline += 2 if tday <= until else 1
        room = target["cap"] - baseline
        if extra <= 0 or room <= 0:
            return 0
        return extra if extra < room else room

    fast_gain._runtime_accelerated = True
    fast_gain._python_fallback = original
    ns["_r51_input_gain"] = fast_gain


def _install_native_r51(module: ModuleType) -> None:
    """Replace only the hot beam-search core when the optional extension exists."""
    if _native is None:
        return
    ns = module.__dict__
    original = ns.get("_r51_input_path")
    start_fn = ns.get("_r62_input_start")
    price_fn = ns.get("_r37_market_price")
    if not callable(original) or not callable(start_fn) or not callable(price_fn):
        return
    if getattr(original, "_native_accelerated", False):
        return

    def accelerated(obs, targets, action, index):
        try:
            step = int(obs["step"])
            day = step // 24
            ready, start = start_fn(obs, action, index)
            market = obs["market"]
            prices = market["prices"]
            wheat_price = max(1, int(prices["WHEAT"]) - 2)
            carrot_price = max(1, int(prices["CARROT"]) - 2)
            fertilizer = max(
                1,
                price_fn("FERTILIZER", market["inventory"]["FERTILIZER"] - 16) + 2,
            )
            return _native.r51_input_path_core(
                targets,
                int(ready),
                start,
                int(day),
                int(wheat_price),
                int(carrot_price),
                int(fertilizer),
            )
        except Exception:
            return original(obs, targets, action, index)

    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r51_input_path"] = accelerated


def _install_native_similarity(module: ModuleType) -> None:
    """Use allocation-free C++ layout comparison when available."""
    if _native is None or not hasattr(_native, "r37_similarity"):
        return
    ns = module.__dict__
    original = ns.get("_r37_similarity")
    if not callable(original) or getattr(original, "_native_accelerated", False):
        return

    def accelerated(observation):
        try:
            return _native.r37_similarity(observation)
        except Exception:
            return original(observation)

    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r37_similarity"] = accelerated


def optimize_agent_module(module: ModuleType) -> ModuleType:
    """Install safe runtime speedups without changing submission compatibility."""
    if module.__dict__.get("copy") is _copy:
        module.__dict__["copy"] = _CopyProxy()
    planner = module.__dict__.get("_PLANNER_NS")
    if isinstance(planner, dict) and planner.get("deepcopy") is _copy.deepcopy:
        planner["deepcopy"] = fast_deepcopy
    _install_fast_gain(module)
    _install_native_r51(module)
    _install_native_similarity(module)
    return module


def native_acceleration_available() -> bool:
    return _native is not None
