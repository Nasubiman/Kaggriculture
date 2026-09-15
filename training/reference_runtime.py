"""Validated native-runtime policies for fixed reference opponents.

Unknown model names are deliberately left untouched.  This module exists so
search/evaluation code can reuse the exact parity policy verified by CI instead
of open-coding native wrappers in individual benchmark scripts.
"""
from __future__ import annotations

from types import ModuleType

import agent_runtime

# Empty tuple means the full shared native stack is trajectory-parity validated.
# Non-empty tuples name accelerated wrappers that must be restored to Python.
REFERENCE_NATIVE_POLICIES: dict[str, tuple[str, ...]] = {
    "public_v31": (),
    "public_v35": (),
    "public_v36": (),
    "public_v37": ("Chassis.act", "_r51_input_control"),
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


def optimize_reference_agent_module(module: ModuleType, model_name: str) -> ModuleType:
    """Apply only a CI-validated native policy for ``model_name``.

    Unknown references are returned without any runtime rewriting.  That makes
    opt-in safe for evaluation/search loaders even when new opponent snapshots
    are added to ``test/`` before their parity policy has been verified.
    """
    restores = REFERENCE_NATIVE_POLICIES.get(model_name)
    if restores is None:
        return module
    agent_runtime.optimize_agent_module(module)
    for target in restores:
        _restore_target(module, target)
    module.__dict__["_REFERENCE_NATIVE_POLICY"] = {
        "model": model_name,
        "restores": restores,
    }
    return module


def validated_reference(model_name: str) -> bool:
    return model_name in REFERENCE_NATIVE_POLICIES
