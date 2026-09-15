#!/usr/bin/env python3
"""Build and activate experimental native runtime accelerators.

The R97 supply kernel and Struct-aware View fast path stay separate from the
permanent native module set until parity and benchmark results justify folding
them in.
"""
from __future__ import annotations

import platform
import shlex
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
SRC = ROOT / "training" / "native_supply.cpp"
OUT = ROOT / "training" / f"_kaggriculture_supply{EXT}"
RUNTIME = ROOT / "training" / "agent_runtime.py"
MARKER = "# native-r97-supply-v1"


def host_flags():
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return ["-march=native", "-mtune=native"]
    if machine in {"arm64", "aarch64"}:
        return ["-mcpu=native"]
    return []


def build() -> None:
    includes = subprocess.check_output(
        [sys.executable, "-m", "pybind11", "--includes"], text=True
    ).strip()
    cmd = [
        "c++", "-O3", "-DNDEBUG", "-shared", "-std=c++17", "-fPIC",
        *host_flags(), *shlex.split(includes), f"-I{ROOT / 'training'}",
        str(SRC), "-o", str(OUT),
    ]
    print(" ".join(shlex.quote(x) for x in cmd), flush=True)
    subprocess.run(cmd, check=True)
    print(OUT, flush=True)


def activate() -> None:
    text = RUNTIME.read_text()
    if MARKER in text:
        return
    text += r'''

# native-r97-supply-v1
try:
    import _kaggriculture_supply as _r97_supply_native
    _pre_supply_optimize_agent_module = optimize_agent_module

    def _struct_get(value, key, default=None):
        if type(value) is dict:
            return value.get(key, default)
        try:
            return value[key]
        except Exception:
            return getattr(value, key, default)

    def _struct_dict(value):
        if type(value) is dict:
            return value
        if value is None:
            return {}
        return dict(value)

    def _install_struct_fast_view(module):
        view_cls = module.__dict__.get("_View")
        if view_cls is None:
            return
        current = getattr(view_cls, "__init__", None)
        if not callable(current) or getattr(current, "_struct_runtime_accelerated", False):
            return

        def accelerated(self, observation, player, cfg):
            if type(observation) is dict:
                return current(self, observation, player, cfg)
            try:
                farms = _struct_get(observation, "farms", ()) or ()
                self.farm = farms[player] if player < len(farms) else {}
                self.rival = farms[1-player] if len(farms) >= 2 and 1-player < len(farms) else {}
                private = _struct_get(observation, "private", {}) or {}
                market = _struct_get(observation, "market", {}) or {}
                self.shed = _struct_dict(_struct_get(private, "shed", {}) or {})
                self.seeds = _struct_dict(_struct_get(private, "seeds", {}) or {})
                raw_invs = _struct_get(private, "inventories", ()) or ()
                self.invs = [inv if type(inv) is dict else _struct_dict(inv) for inv in raw_invs]
                self.prices = _struct_dict(_struct_get(market, "prices", {}) or {})
                self.money = float(_struct_get(self.farm, "money", 0.0) or 0.0)
                self.tiles = _struct_get(self.farm, "tiles", ()) or ()
                self.board = len(self.tiles) or cfg["board_size"]
                farmer = _struct_get(self.farm, "farmer", None)
                hands = _struct_get(self.farm, "hands", ()) or ()
                self.positions = [farmer, *hands]
                self.hires_today = int(_struct_get(self.farm, "hires_today", 0) or 0)
                self.quadrants = len(_struct_get(self.farm, "unlocked_quadrants", ()) or ())
            except Exception:
                return current(self, observation, player, cfg)

        accelerated._runtime_accelerated = True
        accelerated._struct_runtime_accelerated = True
        accelerated._python_fallback = getattr(current, "_python_fallback", current)
        view_cls.__init__ = accelerated

    def optimize_agent_module(module):
        module = _pre_supply_optimize_agent_module(module)
        # benchmark_native_agent_runtime deliberately clears _native for its
        # Python baseline. Keep all experimental additions behind the same
        # master switch so parity/timing comparisons remain uncontaminated.
        if _native is None:
            return module

        _install_struct_fast_view(module)
        ns = module.__dict__
        original = ns.get("_r97_supply")
        impl = ns.get("_IMPL")
        planner = ns.get("_PLANNER_NS")
        report = ns.get("_R97_REPORT")
        budget = ns.get("_r97_budget")
        stock = ns.get("_r97_market_stock")
        delivery = ns.get("_r97_delivery")
        kernel = getattr(_r97_supply_native, "r97_supply", None)
        if (
            callable(original) and callable(kernel) and impl is not None
            and isinstance(planner, dict) and isinstance(report, dict)
            and callable(budget) and callable(stock) and callable(delivery)
            and not getattr(original, "_native_supply_accelerated", False)
        ):
            fallback = getattr(original, "_python_fallback", original)
            diagnostic = {"calls": 0, "fallbacks": 0, "first": None}
            ns["_NATIVE_SUPPLY_DIAGNOSTIC"] = diagnostic

            def accelerated(obs, action):
                try:
                    result = kernel(
                        obs, action, impl, planner, report,
                        budget, stock, delivery,
                    )
                    diagnostic["calls"] += 1
                    return result
                except Exception as exc:
                    diagnostic["fallbacks"] += 1
                    if diagnostic["first"] is None:
                        diagnostic["first"] = f"{type(exc).__name__}: {exc}"
                    return fallback(obs, action)

            accelerated._native_accelerated = True
            accelerated._native_supply_accelerated = True
            accelerated._python_fallback = fallback
            ns["_r97_supply"] = accelerated
        return module
except Exception:
    pass
'''
    RUNTIME.write_text(text)


def main() -> None:
    build()
    activate()


if __name__ == "__main__":
    main()
