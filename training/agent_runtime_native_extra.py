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


def _install_native_deepcopy(module: ModuleType, agent_runtime) -> None:
    native=getattr(agent_runtime,"_native",None)
    native_copy=getattr(native,"deepcopy_builtin",None) if native is not None else None
    if native_copy is None:return
    current=agent_runtime.fast_deepcopy
    if getattr(current,"_native_accelerated",False):
        accelerated=current
    else:
        def accelerated(value,memo=None):
            # Existing memo belongs to an outer Python deepcopy operation. Keep
            # that path in Python so aliases shared with the outer object graph
            # continue to use the same memo table.
            if memo is not None:return current(value,memo)
            try:return native_copy(value)
            except Exception:return current(value)
        accelerated._native_accelerated=True
        accelerated._python_fallback=current
        agent_runtime.fast_deepcopy=accelerated
        agent_runtime._CopyProxy.deepcopy=staticmethod(accelerated)
    planner=module.__dict__.get("_PLANNER_NS")
    if isinstance(planner,dict):
        existing=planner.get("deepcopy")
        if existing is current or getattr(existing,"_native_accelerated",False):
            planner["deepcopy"]=accelerated


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
    for name,native_name in (("_r37_quote_priority","r37_quote_priority"),("_r97_market_stock","market_stock"),("_r97_delivery","delivery")):
        _wrap(ns,name,getattr(_sales_native,native_name,None))
    budget=ns.get("_r97_budget")
    if callable(budget) and hasattr(_sales_native,"budget") and not getattr(budget,"_native_accelerated",False):
        def accelerated_budget(obs,orders):
            if any(o and len(o)>2 and o[0]=="BUY_PRODUCT" and o[1] not in ("WHEAT","FERTILIZER") for o in orders):return budget(obs,orders)
            try:return _sales_native.budget(obs,orders)
            except Exception:return budget(obs,orders)
        accelerated_budget._native_accelerated=True;accelerated_budget._python_fallback=budget;ns["_r97_budget"]=accelerated_budget
    fields=ns.get("_r127_fields")
    if callable(fields) and hasattr(_sales_native,"r127_fields") and not getattr(fields,"_native_accelerated",False):
        def accelerated_fields(obs,action):
            if not action.get("farmer"):return fields(obs,action)
            try:return _sales_native.r127_fields(obs,action)
            except Exception:return fields(obs,action)
        accelerated_fields._native_accelerated=True;accelerated_fields._python_fallback=fields;ns["_r127_fields"]=accelerated_fields


def _install_service(module: ModuleType) -> None:
    if _service_native is None:return
    ns=module.__dict__;impl=ns.get("_IMPL");food=ns.get("_r128_food_need")
    if impl is None:return
    if callable(food) and hasattr(_service_native,"r128_food_need") and not getattr(food,"_native_accelerated",False):
        def accelerated_food(obs,farm,private,actor):
            try:return _service_native.r128_food_need(obs,farm,private,actor,impl)
            except Exception:return food(obs,farm,private,actor)
        accelerated_food._native_accelerated=True;accelerated_food._python_fallback=food;ns["_r128_food_need"]=accelerated_food
    service=ns.get("_r128_service");r127_states=ns.get("_R127_STATES");report=ns.get("_R128_REPORT")
    if callable(service) and isinstance(r127_states,dict) and isinstance(report,dict) and hasattr(_service_native,"r128_service") and not getattr(service,"_native_accelerated",False):
        def accelerated_service(obs,action,state):
            try:return _service_native.r128_service(obs,action,state,impl,r127_states,report)
            except Exception:return service(obs,action,state)
        accelerated_service._native_accelerated=True;accelerated_service._python_fallback=service;ns["_r128_service"]=accelerated_service


def install_native_extra(module: ModuleType) -> ModuleType:
    # benchmark_native_agent_runtime sets agent_runtime._native=None for Python baseline.
    try:
        import agent_runtime
        if agent_runtime._native is None:return module
    except Exception:return module
    _install_native_deepcopy(module,agent_runtime)
    _install_input(module);_install_sales(module);_install_service(module);return module
