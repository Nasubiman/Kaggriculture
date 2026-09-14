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
        result.extend(fast_deepcopy(item, memo) for item in value)
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
        result_set.update(fast_deepcopy(item, memo) for item in value)
        return result_set
    return _copy.deepcopy(value, memo)


class _CopyProxy:
    deepcopy = staticmethod(fast_deepcopy)

    def __getattr__(self, name: str) -> Any:
        return getattr(_copy, name)


def _install_native_r51(module: ModuleType) -> None:
    """Replace only the hot beam-search core when the optional extension exists.

    All observation parsing, price calculation, start-state logic and returned
    Kaggle actions remain Python. Any native exception falls back to the exact
    original Python function for that call.
    """
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
                price_fn(
                    "FERTILIZER",
                    market["inventory"]["FERTILIZER"] - 16,
                ) + 2,
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


def optimize_agent_module(module: ModuleType) -> ModuleType:
    """Install safe runtime speedups without changing submission compatibility."""
    if module.__dict__.get("copy") is _copy:
        module.__dict__["copy"] = _CopyProxy()
    planner = module.__dict__.get("_PLANNER_NS")
    if isinstance(planner, dict) and planner.get("deepcopy") is _copy.deepcopy:
        planner["deepcopy"] = fast_deepcopy
    _install_native_r51(module)
    return module


def native_acceleration_available() -> bool:
    return _native is not None
