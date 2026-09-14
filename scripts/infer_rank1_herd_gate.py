#!/usr/bin/env python3
"""Infer a small, cross-validated cow/sheep gate from rank-1 public games."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path


FEATURES = (
    "milk_wool_spread", "price_wheat", "price_fertilizer", "money",
    "opp_hands", "opp_cow", "opp_sheep", "opp_goose", "opp_herd_spread",
    "shops", "yarn_stores", "seat",
)


def gini(rows):
    if not rows: return 0.0
    counts = Counter(row[2] for row in rows); n = len(rows)
    return 1.0 - sum((count / n) ** 2 for count in counts.values())


def leaf(rows):
    counts = Counter(row[2] for row in rows)
    return {"label": counts.most_common(1)[0][0], "n": len(rows), "counts": dict(counts)}


def fit(rows, depth, min_leaf):
    if depth == 0 or len({row[2] for row in rows}) == 1:
        return leaf(rows)
    best = None
    for index, name in enumerate(FEATURES):
        values = sorted({row[1][index] for row in rows})
        for left_value, right_value in zip(values, values[1:]):
            threshold = (left_value + right_value) / 2
            left = [row for row in rows if row[1][index] <= threshold]
            right = [row for row in rows if row[1][index] > threshold]
            if min(len(left), len(right)) < min_leaf: continue
            score = (len(left) * gini(left) + len(right) * gini(right)) / len(rows)
            candidate = (score, index, threshold, left, right)
            if best is None or candidate[:3] < best[:3]: best = candidate
    if best is None: return leaf(rows)
    _, index, threshold, left, right = best
    return {"feature": FEATURES[index], "index": index, "threshold": threshold,
            "n": len(rows), "left": fit(left, depth - 1, min_leaf),
            "right": fit(right, depth - 1, min_leaf)}


def predict(tree, values):
    while "label" not in tree:
        tree = tree["left"] if values[tree["index"]] <= tree["threshold"] else tree["right"]
    return tree["label"]


def render(tree, indent=""):
    if "label" in tree:
        return [f"{indent}=> {tree['label']} (n={tree['n']}, {tree['counts']})"]
    name = tree["feature"]; threshold = tree["threshold"]
    lines = [f"{indent}if {name} <= {threshold:.2f}:"]
    lines += render(tree["left"], indent + "  ")
    lines += [f"{indent}else:"]
    lines += render(tree["right"], indent + "  ")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--adaptation", type=Path, required=True)
    parser.add_argument("--day", type=int, default=6)
    parser.add_argument("--hour", type=int, default=0)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    labels = {int(row["episode_id"]): row["mode"] for row in json.loads(args.adaptation.read_text())
              if row["mode"] in ("cow-heavy", "sheep-heavy")}
    states = {}
    with gzip.open(args.dataset, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line); f = row.get("features", {})
            if int(f.get("day", -1)) == args.day and int(f.get("hour", -1)) == args.hour and int(row["episode"]) in labels:
                states[int(row["episode"])] = tuple(float(f.get(name, 0)) for name in FEATURES)
    rows = [(episode, states[episode], labels[episode]) for episode in sorted(states)]
    lines = ["# Rank-1 herd gate", "", f"- state: day {args.day}, hour {args.hour}",
             f"- classified games: {len(rows)}", ""]
    sign_correct = sum(("cow-heavy" if values[0] > 0 else "sheep-heavy") == label for _, values, label in rows)
    lines += [f"- full-data price-sign accuracy: {sign_correct}/{len(rows)} ({sign_correct/len(rows):.1%})", ""]
    for depth in (1, 2, 3):
        correct = total = 0
        for fold in range(5):
            train = [row for i, row in enumerate(rows) if i % 5 != fold]
            test = [row for i, row in enumerate(rows) if i % 5 == fold]
            tree = fit(train, depth, 10)
            correct += sum(predict(tree, values) == label for _, values, label in test); total += len(test)
        lines += [f"## Depth {depth}", "", f"- five-fold accuracy: {correct}/{total} ({correct/total:.1%})", "", "```text"]
        lines += render(fit(rows, depth, 10)); lines += ["```", ""]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()
