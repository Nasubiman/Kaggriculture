#!/usr/bin/env python3
"""Apply conservative, semantics-preserving speedups to main.py.

The patch deliberately leaves kaggle-environments untouched. Only this agent
module gets a local ``copy`` proxy whose ``deepcopy`` specializes exact builtin
containers and falls back to stdlib for custom/Kaggle objects. It also removes
allocations from shed-adjacency checks, reuses an identical _View snapshot,
and avoids copying the same route action twice on every normal turn.

Before patching, the original is copied verbatim to
training/reference_main_pre_main_speed.py for parity tests.
"""
from __future__ import annotations

from pathlib import Path
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
    """Fast deepcopy for exact JSON-like containers; stdlib fallback otherwise."""
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
    # Tuple/custom object deepcopy keeps exact stdlib semantics.
    return _STD_DEEPCOPY(value, memo)


class _AgentCopyProxy:
    """Module-local copy proxy; never mutates the stdlib copy module."""
    deepcopy = staticmethod(_fast_deepcopy)

    def __getattr__(self, name):
        return getattr(_STDLIB_COPY, name)


copy = _AgentCopyProxy()
'''

VIEW_CACHE_HELPER = r'''

_VIEW_CACHE_KEY = None
_VIEW_CACHE_VALUE = None


def _cached_view(observation, player, cfg):
    """Reuse _View only for the exact same observation/player/config triple."""
    global _VIEW_CACHE_KEY, _VIEW_CACHE_VALUE
    step = _int(_get(observation, "step", 0), 0)
    farms = _get(observation, "farms", None)
    private = _get(observation, "private", None)
    market = _get(observation, "market", None)
    town = _get(observation, "town", None)
    key = (
        id(observation), int(player), id(cfg), step,
        id(farms), id(private), id(market), id(town),
    )
    if key == _VIEW_CACHE_KEY:
        return _VIEW_CACHE_VALUE
    view = _View(observation, player, cfg)
    _VIEW_CACHE_KEY = key
    _VIEW_CACHE_VALUE = view
    return view
'''


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
    if anchor not in text:
        raise RuntimeError("could not find PRODUCTS insertion anchor")
    text = text.replace(anchor, FAST_COPY_HELPER + anchor, 1)

    old_shed = '''def _shed_adjacent(pos, n):\n    return tuple(pos) in _shed_access_tiles(n)\n'''
    new_shed = '''def _shed_adjacent(pos, n):\n    # Same four inner-corner cells, without allocating a list/tuples.\n    x, y = pos\n    half = n // 2\n    return (x == half - 1 or x == half) and (y == half - 1 or y == half)\n'''
    if text.count(old_shed) != 1:
        raise RuntimeError(f"expected one _shed_adjacent body, found {text.count(old_shed)}")
    text = text.replace(old_shed, new_shed, 1)

    chassis_anchor = "\n\n# --------------------------------------------------------------------------- chassis\nclass Chassis:"
    if chassis_anchor not in text:
        raise RuntimeError("could not find _View/Chassis boundary")
    text = text.replace(chassis_anchor, VIEW_CACHE_HELPER + chassis_anchor, 1)

    old_view = "view = _View(observation, player, cfg)"
    view_count = text.count(old_view)
    if view_count < 1:
        raise RuntimeError(f"could not find _View construction site: {view_count}")
    text = text.replace(old_view, "view = _cached_view(observation, player, cfg)")

    # The old code deep-copies the route action, then immediately deep-copies it
    # again into ``raw`` solely for the exception path. On the overwhelmingly
    # common successful path that second copy is discarded. Recreate the same
    # pristine route action only if an exception actually occurs.
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

    MAIN.write_text(text)
    print(
        "patched main.py: local fast deepcopy + lazy fallback copy + "
        f"view cache + shed adjacency ({view_count} view sites)"
    )


if __name__ == "__main__":
    main()
