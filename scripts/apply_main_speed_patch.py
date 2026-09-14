#!/usr/bin/env python3
"""Apply conservative, semantics-preserving speedups to main.py.

The patch deliberately leaves kaggle-environments untouched.  Only this agent
module gets a local ``copy`` proxy whose ``deepcopy`` specializes exact builtin
containers and falls back to stdlib for custom/Kaggle objects.  It also removes
allocations from shed-adjacency checks and reuses the immutable _View snapshot
only during an identical observation/configuration/step.

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

    # Tuple deepcopy has some cycle/sharing subtleties. It is not a dominant
    # cost here, so keep the exact stdlib behavior rather than over-optimizing.
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


def _cached_view(observation, configuration):
    """Reuse _View for repeated nested wrappers on the exact same observation."""
    global _VIEW_CACHE_KEY, _VIEW_CACHE_VALUE
    step = _int(_get(observation, "step", 0), 0)
    player = _int(_get(observation, "player", 0), 0)
    farms = _get(observation, "farms", None)
    private = _get(observation, "private", None)
    market = _get(observation, "market", None)
    town = _get(observation, "town", None)
    key = (
        id(observation), id(configuration), step, player,
        id(farms), id(private), id(market), id(town),
    )
    if key == _VIEW_CACHE_KEY:
        return _VIEW_CACHE_VALUE
    view = _View(observation, configuration)
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

    anchor = "\n\ndef _cfg(configuration, key, default=None):"
    if anchor not in text:
        raise RuntimeError("could not find import/helper insertion anchor")
    text = text.replace(anchor, FAST_COPY_HELPER + anchor, 1)

    old_shed = '''def _shed_adjacent(pos, n):\n    return tuple(pos) in _shed_access_tiles(n)\n'''
    new_shed = '''def _shed_adjacent(pos, n):\n    # Same four inner-corner cells, without allocating a list/tuples.\n    x, y = pos\n    half = n // 2\n    return (x == half - 1 or x == half) and (y == half - 1 or y == half)\n'''
    if text.count(old_shed) != 1:
        raise RuntimeError(f"expected one _shed_adjacent body, found {text.count(old_shed)}")
    text = text.replace(old_shed, new_shed, 1)

    action_anchor = "\n\nclass _Action:"
    if action_anchor not in text:
        raise RuntimeError("could not find _View/_Action boundary")
    text = text.replace(action_anchor, VIEW_CACHE_HELPER + action_anchor, 1)

    old = "view = _View(observation, configuration)"
    count = text.count(old)
    if count < 2:
        raise RuntimeError(f"unexpectedly few _View wrapper sites: {count}")
    text = text.replace(old, "view = _cached_view(observation, configuration)")

    MAIN.write_text(text)
    print(f"patched main.py: local fast deepcopy + view cache + shed adjacency ({count} view sites)")


if __name__ == "__main__":
    main()
