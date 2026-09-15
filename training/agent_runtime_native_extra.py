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
try:
    import _kaggriculture_chassis as _chassis_native
except Exception:
    _chassis_native = None


def _wrap(ns,name,native):
    original=ns.get(name)
    if not callable(original) or native is None or getattr(original,"_native_accelerated",False):return
    def accelerated(*args):
        try:return native(*args)
        except Exception:return original(*args)
    accelerated._native_accelerated=True;accelerated._python_fallback=original;ns[name]=accelerated


def _field(value,key,default=None):
    if type(value) is dict:return value.get(key,default)
    try:return value[key]
    except Exception:return getattr(value,key,default)


def _plain_mapping(value,keys=()):
    if type(value) is dict:return value
    if value is None:return {}
    try:return dict(value)
    except Exception:return {key:_field(value,key) for key in keys if _field(value,key,None) is not None}


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
    module_copy=module.__dict__.get("copy")
    if module_copy is not None and type(module_copy).__name__ in {"_AgentCopyProxy","_CopyProxy"}:
        module.__dict__["copy"]=agent_runtime._CopyProxy()


def _install_similarity_adapter(module: ModuleType, agent_runtime) -> None:
    """Give the dict-typed native kernel a tiny outer shell and share tile data."""
    native=getattr(agent_runtime,"_native",None)
    native_similarity=getattr(native,"r37_similarity",None) if native is not None else None
    current=module.__dict__.get("_r37_similarity")
    if native_similarity is None or not callable(current):return
    original=getattr(current,"_python_fallback",current)
    diagnostic={"count":0,"first":None}
    module.__dict__["_NATIVE_SIMILARITY_DIAGNOSTIC"]=diagnostic
    def accelerated(observation):
        try:
            farms=observation["farms"]
            thin={
                "player": int(observation["player"]),
                "farms": [
                    {"unlocked_quadrants": farms[0]["unlocked_quadrants"], "tiles": farms[0]["tiles"]},
                    {"unlocked_quadrants": farms[1]["unlocked_quadrants"], "tiles": farms[1]["tiles"]},
                ],
            }
            return native_similarity(thin)
        except Exception as exc:
            diagnostic["count"]+=1
            if diagnostic["first"] is None:diagnostic["first"]=f"{type(exc).__name__}: {exc}"
            return original(observation)
    accelerated._native_accelerated=True
    accelerated._python_fallback=original
    module.__dict__["_r37_similarity"]=accelerated


def _install_struct_chassis(module: ModuleType,agent_runtime) -> None:
    """Keep Struct observations on the native Chassis path using shallow shells.

    The base runtime deliberately accepts only exact dict observations.  Kaggle's
    fast runner supplies Struct-like mappings, so that guard sent every turn back
    through Python Chassis.act and rebuilt _View.  The C++ kernel only needs a
    handful of mapping records; adapt those records shallowly and keep tiles,
    positions, and other large sequences shared by reference.
    """
    if _chassis_native is None or not hasattr(_chassis_native,"chassis_act"):return
    chassis_cls=module.__dict__.get("Chassis");view_cls=module.__dict__.get("_View")
    if chassis_cls is None or view_cls is None:return
    current=getattr(chassis_cls,"act",None)
    if not callable(current):return
    original=getattr(current,"_python_fallback",current)
    if getattr(current,"_struct_native_accelerated",False):return
    diagnostic={"native_calls":0,"fallbacks":0,"first":None}
    module.__dict__["_NATIVE_CHASSIS_DIAGNOSTIC"]=diagnostic
    farm_keys=("money","tiles","farmer","hands","hires_today","unlocked_quadrants")
    private_keys=("shed","seeds","inventories")
    market_keys=("prices",)
    def accelerated(self,observation,configuration=None):
        # Exact dict observations are already handled efficiently by the base
        # wrapper.  Only adapt the Struct-like path here.
        if type(observation) is dict:return current(self,observation,configuration)
        st=None;step=0
        try:
            farms=_field(observation,"farms",()) or ()
            if len(farms)<2:return original(self,observation,configuration)
            farm0=_plain_mapping(farms[0],farm_keys);farm1=_plain_mapping(farms[1],farm_keys)
            private_src=_field(observation,"private",{}) or {}
            private=_plain_mapping(private_src,private_keys)
            invs=private.get("inventories") or []
            if any(type(inv) is not dict for inv in invs):
                private=dict(private);private["inventories"]=[_plain_mapping(inv) for inv in invs]
            if type(private.get("shed")) is not dict:
                private=dict(private);private["shed"]=_plain_mapping(private.get("shed"))
            if type(private.get("seeds")) is not dict:
                private=dict(private);private["seeds"]=_plain_mapping(private.get("seeds"))
            market=_plain_mapping(_field(observation,"market",{}) or {},market_keys)
            if type(market.get("prices")) is not dict:
                market=dict(market);market["prices"]=_plain_mapping(market.get("prices"))
            step=int(_field(observation,"step",0) or 0);player=int(_field(observation,"player",0) or 0)
            thin={"step":step,"player":player,"farms":[farm0,farm1],"private":private,"market":market}
            st=self._state(player,step)
            route=self.router(observation,step,st["router_state"])
            if route not in self.routes:
                route=st["route"] if st["route"] in self.routes else next(iter(self.routes))
            st["route"]=route
            # EXP-167 monkey-patches Chassis._sell_lead so the ordinary lead-sale
            # layer is disabled while R36 reservation logic owns steps 216..695.
            # The C++ chassis bypasses Python method dispatch, so mirror that
            # override through the configuration flag only for the native call.
            r36_window=216<=step<696
            had_sell_lead="sell_lead" in self.cfg
            previous_sell_lead=self.cfg.get("sell_lead")
            if r36_window:self.cfg["sell_lead"]=False
            try:
                result=_chassis_native.chassis_act(self,thin,st,route,view_cls)
            finally:
                if r36_window:
                    if had_sell_lead:self.cfg["sell_lead"]=previous_sell_lead
                    else:self.cfg.pop("sell_lead",None)
            diagnostic["native_calls"]+=1
            return result
        except Exception as exc:
            diagnostic["fallbacks"]+=1
            if diagnostic["first"] is None:diagnostic["first"]=f"{type(exc).__name__}: {exc}"
            # Match the guarded base native wrapper's exceptional behavior after
            # state/router work has begun; otherwise use the exact Python path.
            if st is None:return original(self,observation,configuration)
            self.diagnostics["layer_fallbacks"]=self.diagnostics.get("layer_fallbacks",0)+1
            try:
                route=st.get("route");tape=self.routes.get(route,next(iter(self.routes.values())))
                if 0<=step<len(tape):return agent_runtime.fast_deepcopy(tape[step])
            except Exception:pass
            return {"farmer":["PASS"],"hands":[],"market":[]}
    accelerated._native_accelerated=True
    accelerated._struct_native_accelerated=True
    accelerated._python_fallback=original
    chassis_cls.act=accelerated


def _install_r36_due_suppression(module: ModuleType) -> None:
    """Restore the R36 monkey-patched suppression skipped by C++ Chassis.

    main.py replaces Chassis._apply_suppression with _r36_suppress, which consumes
    reservations due on the current step while retaining zero-quantity SELL slots.
    The C++ chassis calls its internal suppression helper directly, so perform that
    extra debt step immediately before the native reserve layer runs.
    """
    ns=module.__dict__;current=ns.get("_r36_reserve");impl=ns.get("_IMPL")
    if not callable(current) or impl is None or getattr(current,"_r36_due_suppression",False):return
    def accelerated(obs,action):
        try:
            step=int(obs["step"]);player=int(obs["player"])
            state=impl.chassis.players.get(player)
            if state:
                debts=state.get("sell_state",{}).get("r36_debts",{})
                due=debts.pop(step,{})
                if due:
                    for order in action.get("market",[]):
                        if len(order)>=3 and order[0]=="SELL":
                            remaining=due.get(order[1],0)
                            if remaining>0:
                                removed=min(max(0,int(order[2])),remaining)
                                order[2]=int(order[2])-removed
                                due[order[1]]=remaining-removed
        except Exception:
            # Preserve the pre-existing guarded reserve behavior on unusual input.
            pass
        return current(obs,action)
    accelerated._native_accelerated=True
    accelerated._r36_due_suppression=True
    accelerated._python_fallback=getattr(current,"_python_fallback",current)
    ns["_r36_reserve"]=accelerated


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
    _install_similarity_adapter(module,agent_runtime)
    _install_struct_chassis(module,agent_runtime)
    _install_r36_due_suppression(module)
    _install_input(module);_install_sales(module);_install_service(module);return module
