"""Additional native agent accelerators kept separate for guarded rollout."""
from __future__ import annotations
from types import ModuleType

try:
    import _kaggriculture_input as _input_native
except Exception:
    _input_native = None
try:
    import _kaggriculture_sales as _sales_native
except Exception:
    _sales_native = None


def _install_input(module: ModuleType) -> None:
    if _input_native is None or not hasattr(_input_native, "r51_input_control"):
        return
    ns=module.__dict__;original=ns.get("_r51_input_control");impl=ns.get("_IMPL")
    v219=ns.get("_V219_STATES");v233=ns.get("_V233_STATES");report=ns.get("_R51_INPUT_REPORT")
    if not callable(original) or impl is None or not isinstance(v219,dict) or not isinstance(v233,dict) or not isinstance(report,dict) or getattr(original,"_native_accelerated",False):return
    def accelerated(obs,action,state):
        try:return _input_native.r51_input_control(obs,action,state,impl,v219,v233,report)
        except Exception:return original(obs,action,state)
    accelerated._native_accelerated=True;accelerated._python_fallback=original;ns["_r51_input_control"]=accelerated


def _install_sales(module: ModuleType) -> None:
    if _sales_native is None or not hasattr(_sales_native,"r37_quote_priority"):return
    ns=module.__dict__;original=ns.get("_r37_quote_priority")
    if not callable(original) or getattr(original,"_native_accelerated",False):return
    def accelerated(observation,order,stock):
        try:return _sales_native.r37_quote_priority(observation,order,stock)
        except Exception:return original(observation,order,stock)
    accelerated._native_accelerated=True;accelerated._python_fallback=original;ns["_r37_quote_priority"]=accelerated


def install_native_extra(module: ModuleType) -> ModuleType:
    # The benchmark deliberately sets agent_runtime._native=None for its Python baseline.
    try:
        import agent_runtime
        if agent_runtime._native is None:return module
    except Exception:return module
    _install_input(module);_install_sales(module);return module
