#!/usr/bin/env python3
"""Print the important scores from one structured-strategy run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RESULTS = (
    ("current", ("heldout_vs_current_fast.json", "heldout_vs_current_fast_400.json")),
    ("fast", ("parity_fast.json", "parity_fast_40.json")),
    ("standard", ("parity_standard.json", "parity_standard_40.json")),
    ("submission", ("gate_submission_tar_fast.json",)),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()

    if not (args.run / "best_genome.json").is_file():
        raise SystemExit(f"best_genome.json not found in {args.run}")
    print(f"run: {args.run}")
    for label, filenames in RESULTS:
        path = next(
            (args.run / filename for filename in filenames if (args.run / filename).is_file()),
            None,
        )
        if path is None:
            print(f"{label:10} not evaluated")
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
        print(
            f"{label:10} "
            f"wins={summary['wins']}/{summary['games']} "
            f"rate={summary['win_rate']:.1%} "
            f"margin={summary['mean_margin']:.1f} "
            f"reward={summary['mean_reward']:.1f} "
            f"errors={summary['errors']}"
        )


if __name__ == "__main__":
    main()
