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
try:
    import _kaggriculture_service as _service_native
except Exception:
    _service_native = None


def _wrap(ns,name,native):
    original=ns.get(name)
    if not callable(original) or native is None or getattr(original,"_native_accelerated",False):return
    def accelerated(*args):
        try:return native(*args)
        except Exception:return original(*args)
    accelerated._native_accelerated=True;accelerated._python_fallback=original;ns[name]=accelerated


def _install_input(module: ModuleType) -> None:
    if _input_native is None or not hasattr(_input_native,"r51_input_control"):return
    ns=module.__dict__;original=ns.get("_r51_input_control");impl=ns.get("_IMPL");v219=ns.get("_V219_STATES");v233=ns.get("_V233_STATES");report=ns.get("_R51_INPUT_REPORT")
    if not callable(original) or impl is None or not isinstance(v219,dict) or not isinstance(v233,dict) or not isinstance(report,dict) or getattr(original,"_native_accelerated",False):return
    def accelerated(obs,action,state):
        try:return _input_native.r51_input_control(obs,action,state,impl,v219,v233,report)
        except Exception:return original(obs,action,state)
    accelerated._native_accelerated=True;accelerated._python_fallback=original;ns["_r51_input_control"]=accelerated


def _install_sales(module: ModuleType) -> None:
    if _sales_native is None:return
    ns=module.__dict__
    for name,native_name in (("_r37_quote_priority","r37_quote_priority"),("_r97_market_stock","market_stock"),("_r97_delivery","delivery"),("_r97_budget","budget"),("_r127_fields","r127_fields")):
        _wrap(ns,name,getattr(_sales_native,native_name,None))


def _install_service(module: ModuleType) -> None:
    if _service_native is None:return
    ns=module.__dict__;planner=ns.get("_PLANNER_NS");impl=ns.get("_IMPL")
    if not isinstance(planner,dict) or impl is None:return
    # _r127_fields is handled by _kaggriculture_sales, whose unit-action
    # interpreter is native too. Keep service for the future-food lookahead.
    apply_unit=planner.get("_apply_unit_action");food=ns.get("_r128_food_need")
    if callable(food) and callable(apply_unit) and hasattr(_service_native,"r128_food_need") and not getattr(food,"_native_accelerated",False):
        def accelerated_food(obs,farm,private,actor):
            try:return _service_native.r128_food_need(obs,farm,private,actor,impl,apply_unit)
            except Exception:return food(obs,farm,private,actor)
        accelerated_food._native_accelerated=True;accelerated_food._python_fallback=food;ns["_r128_food_need"]=accelerated_food


def install_native_extra(module: ModuleType) -> ModuleType:
    # benchmark_native_agent_runtime sets agent_runtime._native=None for Python baseline.
    try:
        import agent_runtime
        if agent_runtime._native is None:return module
    except Exception:return module
    _install_input(module);_install_sales(module);_install_service(module);return module
