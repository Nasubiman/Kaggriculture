#!/usr/bin/env python3
"""Build a self-contained hybrid that switches to other agents for chosen shop pairs.

The primary (main) agent's actions are submitted until step 144. Every
secondary agent sees a copy of each observation from step 0 so its internal
state is warm. At step 144 the first two opened shops pick the agent for the
rest of the game; any error falls back to the primary.

  --assign PET_CAFE,BAKERY=test/pub_harvest_ledger_20260925/main.py  (repeatable)
"""

import argparse
import base64
import zlib
from pathlib import Path

from kaggle_environments.agent import get_last_callable


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main", type=Path, required=True, help="primary agent without any pair hybrid")
    p.add_argument("--assign", action="append", required=True, help="FIRST,SECOND=path/to/agent.py")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()

    main_source = a.main.read_text(encoding="utf-8")
    if "_PAIR_HYBRID_SOURCE" in main_source or "_MPH_SOURCES" in main_source:
        p.error("primary already contains a pair hybrid; pass the plain main")
    if "kaggle_agent =" not in main_source:
        p.error("primary has no kaggle_agent entry")

    sources, entries, table = {}, {}, {}
    for item in a.assign:
        pair, path = item.split("=", 1)
        first, second = pair.split(",")
        path = str(Path(path))
        if path not in sources:
            text = Path(path).read_text(encoding="utf-8")
            sources[path] = base64.b64encode(zlib.compress(text.encode("utf-8"), level=9)).decode("ascii")
            entries[path] = get_last_callable(text, path=path).__name__
        table[(first, second)] = path
    keys = sorted(sources)
    blob = {f"s{i}": sources[k] for i, k in enumerate(keys)}
    entry = {f"s{i}": entries[k] for i, k in enumerate(keys)}
    pairs = {pair: f"s{keys.index(path)}" for pair, path in table.items()}

    extension = f'''

# Ordered day-six shop-pair hybrid (multi). Embedded sources remain complete,
# including their attribution and license notices.
import base64 as _mph_b64
import copy as _mph_copy
import zlib as _mph_zlib

_MPH_SOURCES = {blob!r}
_MPH_ENTRIES = {entry!r}
_MPH_PAIRS = {pairs!r}
_MPH_AGENTS = {{}}
for _mph_key, _mph_src in _MPH_SOURCES.items():
    _mph_ns = {{"__name__": "embedded_pair_" + _mph_key, "__file__": "<embedded-" + _mph_key + ">"}}
    exec(compile(_mph_zlib.decompress(_mph_b64.b64decode(_mph_src)).decode("utf-8"),
                 "<embedded-" + _mph_key + ">", "exec"), _mph_ns)
    _MPH_AGENTS[_mph_key] = _mph_ns[_MPH_ENTRIES[_mph_key]]
del _mph_key, _mph_src, _mph_ns
_MPH_PRIMARY = kaggle_agent
_MPH_SELECTED = {{}}
_MPH_REPORT = {{"shadow_errors": 0, "secondary_errors": 0, "selected_steps": 0, "selected": None}}


def multi_pair_hybrid_agent(observation, configuration=None):
    seat = int(observation["player"])
    step = int(observation["step"])
    if step == 0:
        _MPH_SELECTED[seat] = None
        _MPH_REPORT.update(shadow_errors=0, secondary_errors=0, selected_steps=0, selected=None)
    if step < 144:
        for _agent in _MPH_AGENTS.values():
            try:
                _agent(_mph_copy.deepcopy(observation), configuration)
            except Exception:
                _MPH_REPORT["shadow_errors"] += 1
        return _MPH_PRIMARY(observation, configuration)
    if step == 144:
        shops = tuple((observation.get("town") or {{}}).get("unlocked_shops", [])[:2])
        _MPH_SELECTED[seat] = _MPH_PAIRS.get(shops)
        _MPH_REPORT["selected"] = _MPH_SELECTED[seat]
    key = _MPH_SELECTED.get(seat)
    if key:
        try:
            action = _MPH_AGENTS[key](observation, configuration)
            _MPH_REPORT["selected_steps"] += 1
            return action
        except Exception:
            _MPH_REPORT["secondary_errors"] += 1
            _MPH_SELECTED[seat] = None
    return _MPH_PRIMARY(observation, configuration)


multi_pair_hybrid_agent.__name__ = "kaggle_agent"
multi_pair_hybrid_agent.telemetry = _MPH_REPORT
kaggle_agent = multi_pair_hybrid_agent
'''
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(main_source + extension, encoding="utf-8")
    print(f"wrote {a.output} secondaries={list(entry.values())} pairs={len(pairs)} bytes={a.output.stat().st_size}")


if __name__ == "__main__":
    main()
