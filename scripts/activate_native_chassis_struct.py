#!/usr/bin/env python3
"""Activate the build-time Struct-aware native Chassis entry for CI experiments."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "training" / "agent_runtime.py"
MARKER = "# native-chassis-struct-adapter-v1"

PATCH = r'''

# native-chassis-struct-adapter-v1
try:
    import _kaggriculture_chassis as _struct_chassis_native
    import agent_runtime_native_extra as _native_extra_runtime
    _pre_struct_chassis_optimize_agent_module = optimize_agent_module

    def optimize_agent_module(module):
        module = _pre_struct_chassis_optimize_agent_module(module)
        if _native is None or not hasattr(_struct_chassis_native, "chassis_act_struct"):
            return module
        chassis_cls = module.__dict__.get("Chassis")
        view_cls = module.__dict__.get("_View")
        if chassis_cls is None or view_cls is None:
            return module
        current = getattr(chassis_cls, "act", None)
        if not callable(current) or getattr(current, "_native_struct_shell_accelerated", False):
            return module
        diagnostic = {"native_calls": 0, "fallbacks": 0, "first": None}
        module.__dict__["_NATIVE_CHASSIS_DIAGNOSTIC"] = diagnostic

        def accelerated(self, observation, configuration=None):
            if type(observation) is dict:
                return current(self, observation, configuration)
            st = None
            step = 0
            try:
                farms = observation["farms"]
                if len(farms) < 2:
                    return current(self, observation, configuration)
                step = int(observation["step"])
                player = int(observation["player"])
                st = self._state(player, step)
                route = self.router(observation, step, st["router_state"])
                if route not in self.routes:
                    route = st["route"] if st["route"] in self.routes else next(iter(self.routes))
                st["route"] = route

                r36_window = 216 <= step < 696
                had_sell_lead = "sell_lead" in self.cfg
                previous_sell_lead = self.cfg.get("sell_lead")
                if r36_window:
                    self.cfg["sell_lead"] = False
                try:
                    result = _struct_chassis_native.chassis_act_struct(
                        self, observation, st, route, view_cls
                    )
                finally:
                    if r36_window:
                        if had_sell_lead:
                            self.cfg["sell_lead"] = previous_sell_lead
                        else:
                            self.cfg.pop("sell_lead", None)
                _native_extra_runtime._apply_r36_due(result, st, step)
                diagnostic["native_calls"] += 1
                return result
            except Exception as exc:
                diagnostic["fallbacks"] += 1
                if diagnostic["first"] is None:
                    diagnostic["first"] = f"{type(exc).__name__}: {exc}"
                if st is None:
                    return current(self, observation, configuration)
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
        accelerated._struct_native_accelerated = True
        accelerated._native_struct_shell_accelerated = True
        accelerated._python_fallback = getattr(current, "_python_fallback", current)
        chassis_cls.act = accelerated
        return module
except Exception:
    pass
'''


def main() -> None:
    text = RUNTIME.read_text()
    if MARKER in text:
        print("native Struct chassis activation already present")
        return
    RUNTIME.write_text(text + PATCH)
    print("activated native Struct chassis adapter")


if __name__ == "__main__":
    main()
