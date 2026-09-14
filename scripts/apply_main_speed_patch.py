#!/usr/bin/env python3
"""Apply semantics-preserving speedups to main.py.

This script is intentionally conservative about Kaggle compatibility:
- exact builtin containers use a specialized deepcopy; unknown/custom values
  fall back to stdlib copy.deepcopy;
- _View is cached only inside the exact same observation/configuration/step;
- shed adjacency is rewritten to an allocation-free equivalent predicate.

Before the first patch, the original main.py is copied verbatim to
training/reference_main_pre_main_speed.py for trajectory parity tests.
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
_STD_DEEPCOPY = copy.deepcopy
_FAST_COPY_ATOMIC = frozenset((type(None), bool, int, float, complex, str, bytes, type(Ellipsis), type(NotImplemented)))


def _fast_deepcopy(value, memo=None):
    """Faster deepcopy for exact builtin containers; stdlib fallback otherwise.

    The memo table preserves sharing/cycles for mutable containers.  This is
    deliberately not installed globally: it only replaces deepcopy calls in
    this submitted module, so kaggle-environments and user observations keep
    their normal behavior.
    """
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

    if kind is tuple:
        # Exact tuples used by the agent are acyclic coordinate/action values.
        # Preserve stdlib's optimization of returning the original tuple when
        # every child is immutable/identical.
        copied = []
        changed = False
        for item in value:
            new_item = _fast_deepcopy(item, memo)
            copied.append(new_item)
            changed |= new_item is not item
        out = tuple(copied) if changed else value
        memo[ident] = out
        return out

    return _STD_DEEPCOPY(value, memo)
'''

VIEW_CACHE_HELPER = r'''

_VIEW_CACHE_KEY = None
_VIEW_CACHE_VALUE = None


def _cached_view(observation, configuration):
    """Reuse _View only within an identical player/step observation.

    Nested policy layers repeatedly receive the same observation object during
    one agent call.  Across turns/games, step/player and object identities make
    the key change, so normal Kaggle simulations cannot receive stale state.
    """
    global _VIEW_CACHE_KEY, _VIEW_CACHE_VALUE
    step = _int(_get(observation, "step", 0), 0)
    player = _int(_get(observation, "player", 0), 0)
    farms = _get(observation, "farms", None)
    private = _get(observation, "private", None)
    key = (
        id(observation),
        id(configuration),
        step,
        player,
        id(farms),
        id(private),
    )
    if key == _VIEW_CACHE_KEY:
        return _VIEW_CACHE_VALUE
    view = _View(observation, configuration)
    _VIEW_CACHE_KEY = key
    _VIEW_CACHE_VALUE = view
    return view
'''


def require_once(text: str, old: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, old, 1)


def main() -> None:
    text = MAIN.read_text()
    if MARKER in text:
        print("main.py speed patch already applied")
        return

    if not REFERENCE.exists():
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MAIN, REFERENCE)
        print(f"saved baseline: {REFERENCE.relative_to(ROOT)}")

    # Insert before the first project helper declaration, after imports are done.
    anchor = "\n\ndef _cfg(configuration, key, default=None):"
    if anchor not in text:
        raise RuntimeError("could not find import/helper insertion anchor")
    text = text.replace(anchor, FAST_COPY_HELPER + anchor, 1)

    # Replace all deepcopy calls made by this module. Unknown/custom object types
    # still delegate to the stdlib implementation inside _fast_deepcopy.
    text = text.replace("copy.deepcopy(", "_fast_deepcopy(")
    # The insertion above intentionally captured stdlib deepcopy before this
    # textual replacement. Restore that one assignment if it was rewritten.
    text = text.replace("_STD_DEEPCOPY = _fast_deepcopy", "_STD_DEEPCOPY = copy.deepcopy", 1)

    old_shed = '''def _shed_adjacent(pos, n):\n    return tuple(pos) in _shed_access_tiles(n)\n'''
    new_shed = '''def _shed_adjacent(pos, n):\n    # Equivalent to membership in the four inner shed-corner tiles, without\n    # allocating a four-element list and coordinate tuples on every call.\n    x, y = pos\n    half = n // 2\n    return (x == half - 1 or x == half) and (y == half - 1 or y == half)\n'''
    if text.count(old_shed) != 1:
        raise RuntimeError(f"expected one _shed_adjacent body, found {text.count(old_shed)}")
    text = text.replace(old_shed, new_shed, 1)

    # Add the cache immediately after _View and before the next class.
    action_anchor = "\n\nclass _Action:"
    if action_anchor not in text:
        raise RuntimeError("could not find _View/_Action boundary")
    text = text.replace(action_anchor, VIEW_CACHE_HELPER + action_anchor, 1)

    # Every policy wrapper constructs _View from the same observation/config.
    # Route those sites through the guarded cache. Keep the constructor itself.
    old = "view = _View(observation, configuration)"
    count = text.count(old)
    if count < 2:
        raise RuntimeError(f"unexpectedly few _View wrapper sites: {count}")
    text = text.replace(old, "view = _cached_view(observation, configuration)")

    MAIN.write_text(text)
    print(f"patched main.py: deepcopy + view cache + shed adjacency ({count} cached-view sites)")


if __name__ == "__main__":
    main()
