#!/usr/bin/env python3
"""Append a day-six shop-pair gate to a frozen submission for paired tests.

The generated file is experimental; the source submission is never modified.
"""

import argparse
from pathlib import Path


GATE = '''

# Experimental day-six correction gate. Keep the existing tape router intact.
_SHOP_GATE_PARENT = kaggle_agent
_SHOP_GATE_DEMAND = frozenset(("BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"))

def shop_pair_gate_agent(observation, configuration=None):
    global V9_FERT_FIRST_DAY, V9_CARROT_RATIO, _DP_H
    if int(observation.get("step", 0)) >= 144:
        shops = tuple(observation["town"]["unlocked_shops"][:2])
        demand = sum(shop in _SHOP_GATE_DEMAND for shop in shops)
        low = "YARN_STORE" not in shops and demand <= 1
        high = "YARN_STORE" not in shops and demand >= 2
        V9_FERT_FIRST_DAY = 14 if high and _SHOP_GATE_FERT else 10
        V9_CARROT_RATIO = 1.6 if low and _SHOP_GATE_CARROT else 2.0
        _DP_H = _SHOP_GATE_DP_HOURS if shops == ("PET_CAFE", "BAKERY") and _SHOP_GATE_DP else 12
    else:
        V9_FERT_FIRST_DAY = 10
        V9_CARROT_RATIO = 2.0
        _DP_H = 12
    return _SHOP_GATE_PARENT(observation, configuration)

shop_pair_gate_agent.telemetry = _SHOP_GATE_PARENT.telemetry
kaggle_agent = shop_pair_gate_agent
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("main.py"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fert", action="store_true")
    parser.add_argument("--carrot", action="store_true")
    parser.add_argument("--dp-pet-bakery", action="store_true")
    parser.add_argument("--dp-hours", type=int, default=8)
    args = parser.parse_args()
    if not args.fert and not args.carrot and not args.dp_pet_bakery:
        parser.error("enable at least one correction")
    if not 1 <= args.dp_hours <= 24:
        parser.error("--dp-hours must be between 1 and 24")
    source = args.source.read_text()
    for text in ("V9_FERT_FIRST_DAY = 10", "V9_CARROT_RATIO = 2.0", "_DP_H = 12", "kaggle_agent = cha20_entry_agent"):
        if text not in source:
            parser.error(f"source does not contain expected anchor: {text}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source + f"\n_SHOP_GATE_FERT = {args.fert}\n_SHOP_GATE_CARROT = {args.carrot}\n_SHOP_GATE_DP = {args.dp_pet_bakery}\n_SHOP_GATE_DP_HOURS = {args.dp_hours}\n" + GATE)
    print(args.output)


if __name__ == "__main__":
    main()
