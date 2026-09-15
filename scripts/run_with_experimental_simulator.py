#!/usr/bin/env python3
"""Run an existing project script with the experimental simulator injected.

Example:
  .venv/bin/python scripts/run_with_experimental_simulator.py \
    scripts/evaluate_test_models.py --candidate main.py --seeds 100 --workers 20

The target script can continue importing ``fast_kaggriculture`` normally.  This
wrapper imports the v3 experimental module first, aliases it under that module
name for the child script, and then executes the target in-process.  The stable
source file is not modified.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training"
if str(TRAINING) not in sys.path:
    sys.path.insert(0, str(TRAINING))

import experimental_fast_kaggriculture_v3 as experimental


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: run_with_experimental_simulator.py TARGET_SCRIPT [ARGS ...]"
        )

    target = Path(sys.argv[1])
    if not target.is_absolute():
        target = (ROOT / target).resolve()
    if not target.is_file():
        raise SystemExit(f"target script not found: {target}")

    # Any later `import fast_kaggriculture` in the target resolves to v3.
    # v3 has already imported/stored the stable implementation internally for
    # guarded fallbacks, so this alias does not destroy its fallback path.
    sys.modules["fast_kaggriculture"] = experimental
    sys.argv = [str(target), *sys.argv[2:]]
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
