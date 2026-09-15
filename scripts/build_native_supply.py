#!/usr/bin/env python3
"""Build and activate the experimental native R97 supply guard.

Kept separate from build_native_speedups.py until parity and benchmark results
justify folding it into the permanent native module set.
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

    def optimize_agent_module(module):
        module = _pre_supply_optimize_agent_module(module)
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
