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

try:
    import _kaggriculture_reserve as _reserve_native
except Exception:
    _reserve_native = None

try:
    import _kaggriculture_controller as _controller_native
except Exception:
    _controller_native = None

try:
    import _kaggriculture_chassis as _chassis_native
except Exception:
    _chassis_native = None

try:
    import _kaggriculture_budget as _budget_native
except Exception:
    _budget_native = None


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


def _install_fast_view(module: ModuleType) -> None:
    view_cls = module.__dict__.get("_View")
    if view_cls is None:
        return
    original = getattr(view_cls, "__init__", None)
    if not callable(original) or getattr(original, "_runtime_accelerated", False):
        return
    def accelerated(self, observation, player, cfg):
        try:
            if type(observation) is not dict:
                raise TypeError
            farms = observation["farms"]
            if type(farms) not in (list, tuple):
                raise TypeError
            self.farm = farms[player] if player < len(farms) else {}
            self.rival = farms[1 - player] if len(farms) >= 2 and 1 - player < len(farms) else {}
            if type(self.farm) is not dict:
                raise TypeError
            private = observation.get("private") or {}
            market = observation.get("market") or {}
            if type(private) is not dict or type(market) is not dict:
                raise TypeError
            self.shed = private.get("shed") or {}
            self.seeds = private.get("seeds") or {}
            self.invs = private.get("inventories") or []
            self.prices = market.get("prices") or {}
            self.money = float(self.farm.get("money", 0.0) or 0.0)
            self.tiles = self.farm.get("tiles") or []
            self.board = len(self.tiles) or cfg["board_size"]
            self.positions = [self.farm.get("farmer"), *(self.farm.get("hands") or [])]
            self.hires_today = int(self.farm.get("hires_today", 0) or 0)
            self.quadrants = len(self.farm.get("unlocked_quadrants") or [])
        except Exception:
            original(self, observation, player, cfg)
    accelerated._runtime_accelerated = True
    accelerated._python_fallback = original
    view_cls.__init__ = accelerated


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


def _install_native_budget(module: ModuleType) -> None:
    if _budget_native is None or not hasattr(_budget_native, "budget_guard"):
        return
    chassis_cls = module.__dict__.get("Chassis")
    if chassis_cls is None:
        return
    original = getattr(chassis_cls, "_budget_guard", None)
    if not callable(original) or getattr(original, "_native_accelerated", False):
        return
    def accelerated(self, action, view, route, step):
        try:
            _budget_native.budget_guard(self, action, view, route, int(step))
            return None
        except Exception:
            return original(self, action, view, route, step)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    chassis_cls._budget_guard = accelerated


def _install_native_chassis(module: ModuleType) -> None:
    if _chassis_native is None or not hasattr(_chassis_native, "chassis_act"):
        return
    ns = module.__dict__
    chassis_cls = ns.get("Chassis")
    view_cls = ns.get("_View")
    if chassis_cls is None or view_cls is None:
        return
    original = getattr(chassis_cls, "act", None)
    if not callable(original) or getattr(original, "_native_accelerated", False):
        return
    def accelerated(self, observation, configuration=None):
        if type(observation) is not dict:
            return original(self, observation, configuration)
        farms = observation.get("farms") or []
        if type(farms) not in (list, tuple) or len(farms) < 2:
            return original(self, observation, configuration)
        try:
            step = int(observation.get("step", 0))
            player = int(observation.get("player", 0))
            st = self._state(player, step)
            route = self.router(observation, step, st["router_state"])
            if route not in self.routes:
                route = st["route"] if st["route"] in self.routes else next(iter(self.routes))
            st["route"] = route
            return _chassis_native.chassis_act(self, observation, st, route, view_cls)
        except Exception:
            self.diagnostics["layer_fallbacks"] = self.diagnostics.get("layer_fallbacks", 0) + 1
            try:
                route = st.get("route")
                tape = self.routes.get(route, next(iter(self.routes.values())))
                if 0 <= step < len(tape):
                    return fast_deepcopy(tape[step])
            except Exception:
                pass
            return {"farmer": ["PASS"], "hands": [], "market": []}
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    chassis_cls.act = accelerated


def _install_native_v231(module: ModuleType) -> None:
    if _controller_native is None or not hasattr(_controller_native, "v231_controller"):
        return
    ns = module.__dict__
    original = ns.get("_v231_controller")
    if not callable(original) or getattr(original, "_native_accelerated", False):
        return
    def accelerated(obs, action, state, cap):
        try:
            return _controller_native.v231_controller(obs, action, state, int(cap))
        except Exception:
            return original(obs, action, state, cap)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_v231_controller"] = accelerated


def _install_native_reserve(module: ModuleType) -> None:
    if _reserve_native is None or not hasattr(_reserve_native, "r36_reserve"):
        return
    ns = module.__dict__
    original = ns.get("_r36_reserve")
    impl = ns.get("_IMPL")
    horizons = ns.get("_R37_HORIZONS")
    report = ns.get("_R36_SALE_REPORT")
    if not callable(original) or impl is None or not isinstance(horizons, dict) or not isinstance(report, dict) or getattr(original, "_native_accelerated", False):
        return
    def accelerated(obs, action):
        try:
            player = int(obs["player"])
            native_state = impl.chassis.players[player]
            tape = impl.chassis.routes[native_state["route"]]
            units, reservations = _reserve_native.r36_reserve(
                obs, action, native_state, tape, int(horizons.get(player, 2))
            )
            if units:
                report["sale_reserved_units"] = report.get("sale_reserved_units", 0) + int(units)
            if reservations:
                report["sale_reservations"] = report.get("sale_reservations", 0) + int(reservations)
            return action
        except Exception:
            return original(obs, action)
    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r36_reserve"] = accelerated


def optimize_agent_module(module: ModuleType) -> ModuleType:
    if module.__dict__.get("copy") is _copy:
        module.__dict__["copy"] = _CopyProxy()
    planner = module.__dict__.get("_PLANNER_NS")
    if isinstance(planner, dict) and planner.get("deepcopy") is _copy.deepcopy:
        planner["deepcopy"] = fast_deepcopy
    _install_fast_view(module)
    _install_fast_gain(module)
    _install_native_market_price(module)
    _install_native_start(module)
    _install_native_forecast(module)
    _install_native_r51(module)
    _install_native_joint_plans(module)
    _install_native_similarity(module)
    _install_native_projected_shed(module)
    _install_native_budget(module)
    _install_native_chassis(module)
    _install_native_v231(module)
    _install_native_reserve(module)
    return module


def native_acceleration_available() -> bool:
    return _native is not None
