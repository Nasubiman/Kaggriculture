#!/usr/bin/env python3
"""Validate main.py with Kaggle's raw-file loader and build a submission tarball."""

from __future__ import annotations

import argparse
from pathlib import Path
import tarfile

from kaggle_environments import make
from kaggle_environments.agent import get_last_callable


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--output", type=Path, default=ROOT / "submission_fixed.tar.gz")
    parser.add_argument("--seed", type=int, default=7_654_321)
    args = parser.parse_args()

    agent_path = args.agent.resolve()
    selected = get_last_callable(
        agent_path.read_text(encoding="utf-8"), path=str(agent_path)
    )
    if not callable(selected):
        raise SystemExit("Kaggle raw loader did not select a callable")
    if selected.__name__ not in ("agent", "kaggle_agent"):
        raise SystemExit(
            f"Kaggle would select {selected.__name__!r}, not the submitted agent"
        )

    rewards = []
    for seat in (0, 1):
        agents = [str(agent_path), "random"] if seat == 0 else ["random", str(agent_path)]
        environment = make(
            "kaggriculture",
            configuration={"episodeSteps": 720, "seed": args.seed},
            debug=True,
        )
        environment.run(agents)
        final = environment.steps[-1][seat]
        if str(final.status) != "DONE":
            raise SystemExit(f"validation episode failed at seat {seat}: {final.status}")
        rewards.append(float(final.reward))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, "w:gz") as archive:
        archive.add(agent_path, arcname="main.py")
    with tarfile.open(args.output, "r:gz") as archive:
        names = archive.getnames()
    if names != ["main.py"]:
        raise SystemExit(f"invalid archive layout: {names}")
    print(
        f"validation OK: loader={selected.__name__} "
        f"rewards={rewards} archive={args.output}"
    )


if __name__ == "__main__":
    main()
