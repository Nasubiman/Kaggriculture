#!/usr/bin/env python3
"""Measure fixed-vs-conditional behavior in a compact public-replay dataset."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable


CONDITION_FEATURES = (
    "money", "milk_wool_spread", "price_milk", "price_wool",
    "price_wheat", "price_fertilizer", "cow", "sheep",
    "opp_cow", "opp_sheep", "opp_herd_spread", "land", "pasture",
)


def command_op(command: Any) -> str:
    return str(command[0]) if isinstance(command, list) and command else "PASS"


def market_signature(action: dict[str, Any]) -> str:
    orders = []
    for order in action.get("market", []) or []:
        if not order:
            continue
        op = str(order[0])
        item = str(order[1]) if len(order) > 1 else ""
        quantity = int(order[2]) if len(order) > 2 else 1
        orders.append((op, item, quantity))
    return json.dumps(orders, separators=(",", ":"))


def macro_signature(action: dict[str, Any]) -> str:
    farmer = command_op(action.get("farmer"))
    hands = Counter(command_op(command) for command in action.get("hands", []) or [])
    hand_summary = sorted(hands.items())
    market = json.loads(market_signature(action))
    return json.dumps([farmer, hand_summary, market], separators=(",", ":"))


def exact_signature(action: dict[str, Any]) -> str:
    return json.dumps(action, sort_keys=True, separators=(",", ":"))


def entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if total <= 1 or len(counts) <= 1:
        return 0.0
    raw = -sum((count / total) * math.log(count / total) for count in counts.values())
    return raw / math.log(len(counts))


def short(signature: str, limit: int = 100) -> str:
    value = signature.replace("|", "/")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def med(rows: Iterable[dict[str, Any]], name: str) -> float:
    values = [float(row["features"].get(name, 0)) for row in rows]
    return median(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    args = parser.parse_args()

    by_step: dict[int, list[dict[str, Any]]] = defaultdict(list)
    with gzip.open(args.dataset, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            action = row["action"]
            row["_exact"] = exact_signature(action)
            row["_macro"] = macro_signature(action)
            row["_market"] = market_signature(action)
            by_step[int(row["step"])].append(row)

    step_rows = []
    for step, rows in sorted(by_step.items()):
        exact = Counter(row["_exact"] for row in rows)
        macro = Counter(row["_macro"] for row in rows)
        market = Counter(row["_market"] for row in rows)
        step_rows.append({
            "step": step, "day": step // 24, "hour": step % 24, "observations": len(rows),
            "exact_unique": len(exact), "exact_modal_share": exact.most_common(1)[0][1] / len(rows),
            "macro_unique": len(macro), "macro_modal_share": macro.most_common(1)[0][1] / len(rows),
            "macro_entropy": entropy(macro), "macro_mode": macro.most_common(1)[0][0],
            "market_unique": len(market), "market_modal_share": market.most_common(1)[0][1] / len(rows),
            "market_entropy": entropy(market), "market_mode": market.most_common(1)[0][0],
        })

    # Branch context: at highly variable steps, compare the two most common macro branches.
    branching = []
    candidates = sorted(step_rows, key=lambda row: (row["macro_entropy"], 1-row["macro_modal_share"]), reverse=True)
    for summary in candidates:
        if summary["macro_unique"] < 2 or summary["observations"] < 20:
            continue
        rows = by_step[summary["step"]]
        counts = Counter(row["_macro"] for row in rows)
        branches = []
        for signature, count in counts.most_common(3):
            selected = [row for row in rows if row["_macro"] == signature]
            branches.append({
                "signature": signature, "count": count, "share": count / len(rows),
                "medians": {name: med(selected, name) for name in CONDITION_FEATURES},
            })
        branching.append({**summary, "branches": branches})
        if len(branching) >= 40:
            break

    fixed_macro = [row for row in step_rows if row["macro_modal_share"] >= .90]
    fixed_market = [row for row in step_rows if row["market_modal_share"] >= .90]
    result = {
        "dataset": str(args.dataset), "steps": len(step_rows),
        "macro_fixed_90_steps": len(fixed_macro),
        "market_fixed_90_steps": len(fixed_market),
        "mean_macro_modal_share": sum(row["macro_modal_share"] for row in step_rows) / len(step_rows),
        "mean_market_modal_share": sum(row["market_modal_share"] for row in step_rows) / len(step_rows),
        "step_profiles": step_rows, "top_branching_steps": branching,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Rank-1 fixed trajectory vs conditional branching", "",
        f"- Turns analyzed: {len(step_rows)}",
        f"- Macro action modal share (mean): {result['mean_macro_modal_share']:.1%}",
        f"- Market action modal share (mean): {result['mean_market_modal_share']:.1%}",
        f"- Macro action fixed at >=90%: {len(fixed_macro)}/{len(step_rows)} turns",
        f"- Market action fixed at >=90%: {len(fixed_market)}/{len(step_rows)} turns", "",
        "Macro action preserves farmer operation, counts of hand operations, and market orders, but ignores target coordinates.",
        "", "## Most conditional turns", "",
        "| Step | Day/hour | N | Macro variants | Mode share | Entropy | Market mode share | Modal macro action |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in branching[:30]:
        lines.append(
            f"| {row['step']} | d{row['day']} h{row['hour']} | {row['observations']} | "
            f"{row['macro_unique']} | {row['macro_modal_share']:.1%} | {row['macro_entropy']:.2f} | "
            f"{row['market_modal_share']:.1%} | `{short(row['macro_mode'])}` |"
        )
    lines += ["", "## Context of leading branches", ""]
    for row in branching[:15]:
        lines += [f"### Step {row['step']} (day {row['day']}, hour {row['hour']})", "",
                  "| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |",
                  "|---|---:|---:|---:|---:|---:|---|---|---:|"]
        for branch in row["branches"]:
            m = branch["medians"]
            lines.append(
                f"| `{short(branch['signature'], 72)}` | {branch['share']:.1%} | {m['money']:.0f} | "
                f"{m['milk_wool_spread']:.0f} | {m['price_milk']:.0f} | {m['price_wool']:.0f} | "
                f"{m['cow']:.0f}/{m['sheep']:.0f} | {m['opp_cow']:.0f}/{m['opp_sheep']:.0f} | "
                f"{m['opp_herd_spread']:.0f} |"
            )
        lines.append("")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.report}")
    print(f"wrote {args.json_output}")


if __name__ == "__main__":
    main()
