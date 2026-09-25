#!/usr/bin/env python3
"""Extract only DECEM's additive SE-worker trajectory from a public replay.

The source replay is 111847040 (2026-09-22, engine 1.32.7). Its base actor
commands match our current route through day 12. The output is a compact
research tape; it is not a submission model.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from kaggle_environments.agent import get_last_callable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    names = replay["info"]["TeamNames"]
    if "DECEM" not in names or int(replay["info"]["EpisodeId"]) != 111847040:
        parser.error("expected DECEM episode 111847040")
    seat = names.index("DECEM")
    agent = get_last_callable(args.candidate.read_text(encoding="utf-8"),
                              path=str(args.candidate))
    tape: dict[str, dict] = {}
    extra_hires = 0
    last_day = -1
    base_mismatches = 0
    for step in range(len(replay["steps"]) - 1):
        observation = dict(replay["steps"][step][seat]["observation"], step=step)
        predicted = agent(observation)
        actual = replay["steps"][step + 1][seat].get("action") or {}
        if step < 289:
            continue
        day = step // 24
        if day != last_day:
            extra_hires = 0
            last_day = day
        planned_hires = sum(order == ["HIRE"] for order in predicted.get("market") or [])
        actual_hires = sum(order == ["HIRE"] for order in actual.get("market") or [])
        added_hires = actual_hires - planned_hires
        if added_hires < 0:
            raise RuntimeError(f"step {step}: public hires less than base")
        present_extra = extra_hires
        if present_extra and (predicted.get("hands") or [])[:-present_extra] != (
                actual.get("hands") or [])[:-present_extra]:
            base_mismatches += 1
        hands = (actual.get("hands") or [])[-present_extra:] if present_extra else []
        extra_hires += added_hires
        record = {"hire": added_hires}
        if hands:
            record["hands"] = hands
        def purchases(market):
            counts = Counter()
            for order in market or []:
                if len(order) >= 3 and order[0] in ("BUY_SEED", "BUY_PRODUCT"):
                    counts[(order[0], order[1])] += int(order[2])
            return counts
        extra_buys = purchases(actual.get("market")) - purchases(predicted.get("market"))
        if extra_buys:
            record["buys"] = [[op, item, quantity]
                              for (op, item), quantity in extra_buys.items()]
        if step == 289:
            record["land"] = True
        if added_hires or hands or extra_buys or step == 289:
            tape[str(step)] = record
    output = {
        "episode_id": 111847040,
        "seed": replay["info"]["seed"],
        "team": "DECEM",
        "seat": seat,
        "start_step": 289,
        "base_actor_mismatches": base_mismatches,
        "tape": tape,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {args.output}; {len(tape)} steps, "
          f"{sum(row['hire'] for row in tape.values())} extra hires, "
          f"{base_mismatches} base actor mismatches")


if __name__ == "__main__":
    main()
