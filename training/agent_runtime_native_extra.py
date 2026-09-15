"""Additional native agent accelerators kept separate for guarded rollout."""
from __future__ import annotations

from types import ModuleType

try:
    import _kaggriculture_input as _input_native
except Exception:
    _input_native = None


def install_native_extra(module: ModuleType) -> ModuleType:
    if _input_native is None or not hasattr(_input_native, "r51_input_control"):
        return module
    ns = module.__dict__
    original = ns.get("_r51_input_control")
    impl = ns.get("_IMPL")
    v219 = ns.get("_V219_STATES")
    v233 = ns.get("_V233_STATES")
    report = ns.get("_R51_INPUT_REPORT")
    if not callable(original) or impl is None or not isinstance(v219, dict) or not isinstance(v233, dict) or not isinstance(report, dict):
        return module
    if getattr(original, "_native_accelerated", False):
        return module

    def accelerated(obs, action, state):
        try:
            return _input_native.r51_input_control(obs, action, state, impl, v219, v233, report)
        except Exception:
            return original(obs, action, state)

    accelerated._native_accelerated = True
    accelerated._python_fallback = original
    ns["_r51_input_control"] = accelerated
    return module
