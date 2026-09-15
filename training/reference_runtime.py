"""Validated native-runtime policies for fixed reference opponents.

Unknown model names are deliberately left untouched. Search/evaluation code can
reuse the exact parity policy verified by CI instead of open-coding native
wrappers in individual benchmark scripts.
"""
from __future__ import annotations

from types import ModuleType

import agent_runtime

# Empty tuple means the shared native stack is trajectory-parity validated after
# applying the reference-specific reserve activation window below. Non-empty
# tuples name wrappers that still need to be restored to Python.
REFERENCE_NATIVE_POLICIES: dict[str, tuple[str, ...]] = {
    "public_v31": (),
    "public_v35": (),
    "public_v36": (),
    "public_v37": ("Chassis.act", "_r51_input_control"),
    "public_v38_low_pressure_20260914": (),
    "public_v41_competitive_20260914": (),
    "public_v41_survival_20260914": (),
}

# The reserve policy changed activation windows between snapshots. The generic
# runtime keeps the historical 216-step entrypoint for candidate compatibility;
# fixed reference opponents use the exact window encoded in their Python source.
REFERENCE_RESERVE_START: dict[str, int] = {
    "public_v31": 288,
    "public_v35": 288,
    "public_v36": 288,
    "public_v37": 288,
    "public_v38_low_pressure_20260914": 288,
    "public_v41_competitive_20260914": 288,
    "public_v41_survival_20260914": 216,
}


def _unwrap_python(fn):
    seen: set[int] = set()
    while callable(fn) and id(fn) not in seen:
        seen.add(id(fn))
        fallback = getattr(fn, "_python_fallback", None)
        if not callable(fallback):
            break
        fn = fallback
    return fn


def _restore_target(module: ModuleType, target: str) -> None:
    if "." in target:
        owner_name, attr = target.split(".", 1)
        owner = module.__dict__.get(owner_name)
        if owner is None:
            return
        original = _unwrap_python(getattr(owner, attr, None))
        if callable(original):
            setattr(owner, attr, original)
        return
    original = _unwrap_python(module.__dict__.get(target))
    if callable(original):
        module.__dict__[target] = original


def _install_reference_reserve(module: ModuleType, start_step: int) -> None:
    native = getattr(agent_runtime, "_reserve_native", None)
    native_fn = getattr(native, "r36_reserve_with_start", None) if native is not None else None
    ns = module.__dict__
    current = ns.get("_r36_reserve")
    original = _unwrap_python(current)
    impl = ns.get("_IMPL")
    horizons = ns.get("_R37_HORIZONS")
    report = ns.get("_R36_SALE_REPORT")
    if (
        native_fn is None
        or not callable(original)
        or impl is None
        or not isinstance(horizons, dict)
        or not isinstance(report, dict)
    ):
        # If the policy-capable native entrypoint was not built, exact semantics
        # are preferable to silently using the generic 216-step wrapper.
        if callable(original):
            ns["_r36_reserve"] = original
        return

    def accelerated(obs, action):
        try:
            player = int(obs["player"])
            native_state = impl.chassis.players[player]
            tape = impl.chassis.routes[native_state["route"]]
            units, reservations = native_fn(
                obs,
                action,
                native_state,
                tape,
                int(horizons.get(player, 2)),
                int(start_step),
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
    accelerated._reference_start_step = int(start_step)
    ns["_r36_reserve"] = accelerated


def optimize_reference_agent_module(module: ModuleType, model_name: str) -> ModuleType:
    """Apply only the CI-validated native policy for ``model_name``.

    Unknown references are returned without runtime rewriting, so adding a new
    snapshot under test/ cannot silently change its semantics.
    """
    restores = REFERENCE_NATIVE_POLICIES.get(model_name)
    if restores is None:
        return module
    agent_runtime.optimize_agent_module(module)
    _install_reference_reserve(module, REFERENCE_RESERVE_START[model_name])
    for target in restores:
        _restore_target(module, target)
    module.__dict__["_REFERENCE_NATIVE_POLICY"] = {
        "model": model_name,
        "reserve_start": REFERENCE_RESERVE_START[model_name],
        "restores": restores,
    }
    return module


def validated_reference(model_name: str) -> bool:
    return model_name in REFERENCE_NATIVE_POLICIES
