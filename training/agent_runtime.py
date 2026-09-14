"""Runtime-only accelerators for trusted pure-Python competition agents."""

from __future__ import annotations

import copy as _copy
from types import ModuleType
from typing import Any


_ATOMIC = (type(None), bool, int, float, str, bytes)


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


def optimize_agent_module(module: ModuleType) -> ModuleType:
    """Install faster container copying without mutating the stdlib copy module."""
    if module.__dict__.get("copy") is _copy:
        module.__dict__["copy"] = _CopyProxy()
    planner = module.__dict__.get("_PLANNER_NS")
    if isinstance(planner, dict) and planner.get("deepcopy") is _copy.deepcopy:
        planner["deepcopy"] = fast_deepcopy
    return module
