#!/usr/bin/env python3
"""Build a self-contained shop-pair hybrid from the current main and a public agent.

Both policies observe the real opening; only main.py's actions are submitted
before the first two shops are revealed. The secondary agent is selected only
for the specified ordered shop pair at step 144.
"""

import argparse
import base64
import zlib
from pathlib import Path

from kaggle_environments.agent import get_last_callable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, default=Path("main.py"))
    parser.add_argument("--secondary", type=Path, required=True)
    parser.add_argument("--first-shop", required=True)
    parser.add_argument("--second-shop", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    main_source = args.main.read_text(encoding="utf-8")
    other_source = args.secondary.read_text(encoding="utf-8")
    if "_PAIR_HYBRID_SOURCE =" in main_source:
        parser.error("main source already contains a pair hybrid")
    if "kaggle_agent =" not in main_source:
        parser.error("main source has no kaggle_agent entry")
    other_entry = get_last_callable(other_source, path=str(args.secondary)).__name__
    compressed = base64.b64encode(zlib.compress(other_source.encode("utf-8"), level=9)).decode("ascii")
    extension = f'''

# Ordered day-six shop-pair hybrid. The embedded source remains complete,
# including its attribution and license notices.
import base64 as _pair_b64
import copy as _pair_copy
import zlib as _pair_zlib

_PAIR_HYBRID_SOURCE = {compressed!r}
_PAIR_HYBRID_NS = {{"__name__": "embedded_pair_secondary", "__file__": "<embedded-secondary>"}}
exec(compile(_pair_zlib.decompress(_pair_b64.b64decode(_PAIR_HYBRID_SOURCE)).decode("utf-8"),
             "<embedded-secondary>", "exec"), _PAIR_HYBRID_NS)
_PAIR_HYBRID_SECONDARY = _PAIR_HYBRID_NS[{other_entry!r}]
_PAIR_HYBRID_PRIMARY = kaggle_agent
_PAIR_HYBRID_TARGET = ({args.first_shop!r}, {args.second_shop!r})
_PAIR_HYBRID_SELECTED = {{}}
_PAIR_HYBRID_REPORT = {{"shadow_errors": 0, "secondary_errors": 0, "selected_steps": 0}}

def pair_hybrid_agent(observation, configuration=None):
    seat = int(observation["player"])
    step = int(observation["step"])
    if step == 0:
        _PAIR_HYBRID_SELECTED[seat] = None
        _PAIR_HYBRID_REPORT.update(shadow_errors=0, secondary_errors=0, selected_steps=0)
    if step < 144:
        try:
            _PAIR_HYBRID_SECONDARY(_pair_copy.deepcopy(observation), configuration)
        except Exception:
            _PAIR_HYBRID_REPORT["shadow_errors"] += 1
        return _PAIR_HYBRID_PRIMARY(observation, configuration)
    if step == 144:
        shops = tuple((observation.get("town") or {{}}).get("unlocked_shops", [])[:2])
        _PAIR_HYBRID_SELECTED[seat] = shops == _PAIR_HYBRID_TARGET
    if _PAIR_HYBRID_SELECTED.get(seat):
        try:
            action = _PAIR_HYBRID_SECONDARY(observation, configuration)
            _PAIR_HYBRID_REPORT["selected_steps"] += 1
            return action
        except Exception:
            _PAIR_HYBRID_REPORT["secondary_errors"] += 1
            _PAIR_HYBRID_SELECTED[seat] = False
    return _PAIR_HYBRID_PRIMARY(observation, configuration)

pair_hybrid_agent.__name__ = "kaggle_agent"
pair_hybrid_agent.telemetry = _PAIR_HYBRID_REPORT
kaggle_agent = pair_hybrid_agent
'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(main_source + extension, encoding="utf-8")
    print(f"wrote {args.output} secondary={other_entry} bytes={args.output.stat().st_size}")


if __name__ == "__main__":
    main()
