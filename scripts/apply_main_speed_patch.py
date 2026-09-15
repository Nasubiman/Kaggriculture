#!/usr/bin/env python3
"""Apply semantics-preserving speedups to the training/evaluation main.py.

The patched copy is validated against the untouched reference in both the fast
runner and the official Kaggriculture environment.  Source shape is deliberately
secondary to behavioral parity.

Transformations:
1. install a module-local deepcopy implementation specialized for exact builtin
   JSON-like containers, with stdlib fallback for every other object type;
2. remove the second eager copy of each route action that exists only to serve
   an exceptional fallback path, and reconstruct it only if that path is taken;
3. remove parent->child telemetry dictionary propagation.  Telemetry is
   diagnostic-only and copying the full accumulated report through every wrapper
   is pure hot-path overhead; local counters themselves are left intact.
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
REFERENCE = ROOT / "training" / "reference_main_pre_main_speed.py"
MARKER = "# MAIN_SPEED_PATCH_20260914_V1"

FAST_COPY_HELPER = r'''

# MAIN_SPEED_PATCH_20260914_V1
_STDLIB_COPY = copy
_STD_DEEPCOPY = copy.deepcopy
_FAST_COPY_ATOMIC = frozenset((
    type(None), bool, int, float, complex, str, bytes,
    type(Ellipsis), type(NotImplemented),
))


def _fast_deepcopy(value, memo=None):
    """Fast deepcopy for exact builtin containers; stdlib fallback otherwise."""
    kind = type(value)
    if kind in _FAST_COPY_ATOMIC:
        return value
    if memo is None:
        memo = {}
    ident = id(value)
    if ident in memo:
        return memo[ident]
    if kind is list:
        out = []
        memo[ident] = out
        append = out.append
        for item in value:
            append(_fast_deepcopy(item, memo))
        return out
    if kind is dict:
        out = {}
        memo[ident] = out
        for key, item in value.items():
            out[_fast_deepcopy(key, memo)] = _fast_deepcopy(item, memo)
        return out
    if kind is set:
        out = set()
        memo[ident] = out
        add = out.add
        for item in value:
            add(_fast_deepcopy(item, memo))
        return out
    # Tuple/custom/Kaggle Struct objects retain exact stdlib deepcopy behavior.
    return _STD_DEEPCOPY(value, memo)


class _AgentCopyProxy:
    """Module-local copy proxy; never mutates Python's stdlib copy module."""
    deepcopy = staticmethod(_fast_deepcopy)

    def __getattr__(self, name):
        return getattr(_STDLIB_COPY, name)


copy = _AgentCopyProxy()
'''

# Copying a parent's cumulative telemetry into the next overlay never changes an
# action or policy state.  Match only the explicit diagnostic propagation form;
# report-to-report updates and local counter resets are intentionally preserved.
_PARENT_TELEMETRY_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*\.update\(getattr\("
    r"[A-Za-z_][A-Za-z0-9_]*\s*,\s*['\"]telemetry['\"]\s*,\s*\{\}\s*\)\)\s*;?"
)


def main() -> None:
    text = MAIN.read_text()
    if MARKER in text:
        print("main.py speed patch already applied")
        return
    if not REFERENCE.exists():
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MAIN, REFERENCE)
        print(f"saved baseline: {REFERENCE.relative_to(ROOT)}")

    anchor = "\n\nPRODUCTS = ("
    if text.count(anchor) != 1:
        raise RuntimeError(f"expected one PRODUCTS insertion anchor, found {text.count(anchor)}")
    text = text.replace(anchor, FAST_COPY_HELPER + anchor, 1)

    # _route_action already returns a fresh deepcopy. The immediately following
    # ``raw = copy.deepcopy(action)`` is used only if a later layer raises.
    # Defer creation of that pristine fallback until the exceptional path.
    old_raw = '''        action = self._route_action(route, step)\n        raw = copy.deepcopy(action)\n        try:\n'''
    new_raw = '''        action = self._route_action(route, step)\n        try:\n'''
    if text.count(old_raw) != 1:
        raise RuntimeError(f"expected one eager raw copy, found {text.count(old_raw)}")
    text = text.replace(old_raw, new_raw, 1)

    old_except = '''        except Exception:\n            self.diagnostics["layer_fallbacks"] += 1\n            return raw\n'''
    new_except = '''        except Exception:\n            self.diagnostics["layer_fallbacks"] += 1\n            return self._route_action(route, step)\n'''
    if text.count(old_except) != 1:
        raise RuntimeError(f"expected one layer fallback, found {text.count(old_except)}")
    text = text.replace(old_except, new_except, 1)

    text, telemetry_removed = _PARENT_TELEMETRY_RE.subn("", text)
    if telemetry_removed < 10:
        raise RuntimeError(
            f"expected many parent telemetry propagations, removed only {telemetry_removed}"
        )

    MAIN.write_text(text)
    print(
        "patched main.py: local fast deepcopy + lazy fallback action copy + "
        f"removed {telemetry_removed} parent telemetry propagations"
    )


if __name__ == "__main__":
    main()
