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
3. remove diagnostic telemetry/report propagation between wrapper layers while
   preserving each layer's own state and counters;
4. replace the final forwarding kaggle_agent function with direct aliases to the
   configured callable, removing one Python function call per turn.
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
    return _STD_DEEPCOPY(value, memo)


class _AgentCopyProxy:
    deepcopy = staticmethod(_fast_deepcopy)

    def __getattr__(self, name):
        return getattr(_STDLIB_COPY, name)


copy = _AgentCopyProxy()
'''

# Diagnostics are exported to telemetry but never feed the decision path.  Keep
# local report counters because a few native accelerators write them, but stop
# repeatedly copying accumulated dictionaries through the wrapper chain.
_PARENT_TELEMETRY_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*\.update\(getattr\("
    r"[A-Za-z_][A-Za-z0-9_]*\s*,\s*['\"]telemetry['\"]\s*,\s*\{\}\s*\)\)\s*;?"
)
_DIRECT_PARENT_TELEMETRY_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*\.update\("
    r"[A-Za-z_][A-Za-z0-9_]*\.telemetry\)\s*;?"
)
_REPORT_AGGREGATION_RE = re.compile(
    r"(?:[A-Z][A-Z0-9_]*(?:REPORT|COMBINED))\.update\("
    r"[A-Z][A-Z0-9_]*REPORT\)\s*;?"
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

    text, inherited_removed = _PARENT_TELEMETRY_RE.subn("", text)
    text, direct_removed = _DIRECT_PARENT_TELEMETRY_RE.subn("", text)
    text, aggregate_removed = _REPORT_AGGREGATION_RE.subn("", text)
    total_removed = inherited_removed + direct_removed + aggregate_removed
    if inherited_removed < 10 or total_removed < 18:
        raise RuntimeError(
            "expected broad diagnostic propagation removal, got "
            f"inherited={inherited_removed}, direct={direct_removed}, "
            f"aggregate={aggregate_removed}"
        )

    final_wrapper = '''\n\ndef kaggle_agent(obs, config=None):\n    return _configured_current_genome_agent(obs, config)\n\n\nagent = kaggle_agent\n'''
    flattened = '''\n\n# Direct aliases: avoid one Python forwarding call per turn.\nkaggle_agent = _configured_current_genome_agent\nagent = _configured_current_genome_agent\n'''
    if text.count(final_wrapper) != 1:
        raise RuntimeError(
            f"expected one final kaggle_agent forwarding wrapper, found {text.count(final_wrapper)}"
        )
    text = text.replace(final_wrapper, flattened, 1)

    MAIN.write_text(text)
    print(
        "patched main.py: fast deepcopy + lazy fallback + removed diagnostic "
        f"propagation inherited={inherited_removed}, direct={direct_removed}, "
        f"aggregate={aggregate_removed} + flattened final agent wrapper"
    )


if __name__ == "__main__":
    main()
