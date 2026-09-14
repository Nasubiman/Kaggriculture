"""Runtime-only accelerators for trusted pure-Python competition agents."""

from __future__ import annotations

import copy as _copy
from types import ModuleType
from typing import Any

_ATOMIC = (type(None), bool, int, float, str, bytes)

try:
    import _kaggriculture_native as _native
except Exception:
    _native = None


def fast_deepcopy(value: Any, memo: dict[int, Any] | None = None) -> Any:
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
        return 0 if extra <= 0 or room <= 0 else min(extra, room)
    fast_gain._runtime_accelerated = True
    fast_gain._python_fallback = original
    ns["_r51_input_gain"] = fast_gain


def _install_native_market_price(module: ModuleType) -> None:
    if _native is None or not hasattr(_native, "r37_market_price"):
        return
    ns = module.__dict__
    original = ns.get("_r37_market_price")
    if not callable(original) or getattr(original, "_native_accelerated", False):
        return
    def accelerated(item, inventory, params=None):
        if params is not None:
            return original(item, inventory, params)
        try:
            return _native.r37_market_price(str(item), int(inventory))
        except Exception:
            return original(item, inventory)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r37_market_price"] = accelerated


def _install_native_start(module: ModuleType) -> None:
    if _native is None or not hasattr(_native, "r62_input_start"):
        return
    ns = module.__dict__
    original = ns.get("_r62_input_start")
    if not callable(original) or getattr(original, "_native_accelerated", False):
        return
    def accelerated(obs, action, index):
        try:
            return _native.r62_input_start(obs, action, int(index))
        except Exception:
            return original(obs, action, index)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r62_input_start"] = accelerated


def _install_native_forecast(module: ModuleType) -> None:
    if _native is None or not hasattr(_native, "r51_input_forecast"):
        return
    ns = module.__dict__
    original = ns.get("_r51_input_forecast")
    impl = ns.get("_IMPL")
    if not callable(original) or impl is None or getattr(original, "_native_accelerated", False):
        return
    def accelerated(obs, route, expected):
        try:
            routes = impl.chassis.routes
            return _native.r51_input_forecast(obs, routes[route], routes[2], int(expected))
        except Exception:
            return original(obs, route, expected)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r51_input_forecast"] = accelerated


def _install_native_r51(module: ModuleType) -> None:
    if _native is None or not hasattr(_native, "r51_input_path_core"):
        return
    ns = module.__dict__
    original = ns.get("_r51_input_path")
    start_fn = ns.get("_r62_input_start")
    price_fn = ns.get("_r37_market_price")
    if not callable(original) or not callable(start_fn) or not callable(price_fn) or getattr(original, "_native_accelerated", False):
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
            fertilizer = max(1, price_fn("FERTILIZER", market["inventory"]["FERTILIZER"] - 16) + 2)
            return _native.r51_input_path_core(targets, int(ready), start, int(day), int(wheat_price), int(carrot_price), int(fertilizer))
        except Exception:
            return original(obs, targets, action, index)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r51_input_path"] = accelerated


def _install_native_joint_plans(module: ModuleType) -> None:
    if _native is None or not hasattr(_native, "r68_joint_plans"):
        return
    ns = module.__dict__
    original = ns.get("_r68_joint_plans")
    if not callable(original) or getattr(original, "_native_accelerated", False):
        return
    def accelerated(obs, action, targets, stock, purchases, topup):
        try:
            return _native.r68_joint_plans(obs, action, targets, stock, int(purchases), int(topup))
        except Exception:
            return original(obs, action, targets, stock, purchases, topup)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r68_joint_plans"] = accelerated


def _install_native_similarity(module: ModuleType) -> None:
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


def _install_native_projected_shed(module: ModuleType) -> None:
    if _native is None or not hasattr(_native, "projected_shed"):
        return
    chassis_cls = module.__dict__.get("Chassis")
    if chassis_cls is None:
        return
    original = getattr(chassis_cls, "_projected_shed", None)
    if not callable(original) or getattr(original, "_native_accelerated", False):
        return
    def accelerated(self, action, view):
        try:
            return _native.projected_shed(action, view, int(self.cfg["shed_capacity"]))
        except Exception:
            return original(self, action, view)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    chassis_cls._projected_shed = accelerated


def optimize_agent_module(module: ModuleType) -> ModuleType:
    if module.__dict__.get("copy") is _copy:
        module.__dict__["copy"] = _CopyProxy()
    planner = module.__dict__.get("_PLANNER_NS")
    if isinstance(planner, dict) and planner.get("deepcopy") is _copy.deepcopy:
        planner["deepcopy"] = fast_deepcopy
    _install_fast_gain(module)
    _install_native_market_price(module)
    _install_native_start(module)
    _install_native_forecast(module)
    _install_native_r51(module)
    _install_native_joint_plans(module)
    _install_native_similarity(module)
    _install_native_projected_shed(module)
    return module


def native_acceleration_available() -> bool:
    return _native is not None
