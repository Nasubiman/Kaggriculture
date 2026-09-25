#!/usr/bin/env python3
"""Build a self-contained four-quadrant candidate from the current main.py.

The public replay tape is compressed into the submitted Python file. This
program never edits main.py; promote the resulting candidate only after
paired evaluation and official validation.
"""

from __future__ import annotations

import argparse
import base64
import inspect
import json
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
import search_public_four_quadrant as study


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("main.py"))
    parser.add_argument("--tape", type=Path,
                        default=Path("training/decem_se_strawberry_111847040.json"))
    parser.add_argument("--variant", choices=study.VARIANTS,
                        default="early_strawberry_11")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.base.resolve():
        parser.error("output must differ from base; validate before promoting")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing candidate: {args.output}")

    base = args.base.read_text(encoding="utf-8")
    tape = json.loads(args.tape.read_text(encoding="utf-8"))["tape"]
    payload = base64.b85encode(zlib.compress(
        json.dumps(tape, separators=(",", ":")).encode("utf-8"), level=9
    )).decode("ascii")
    overlay = (
        "\n\n# Conditional four-quadrant experiment; source episode 111847040.\n"
        "# The embedded tape and its policy contain no replay outcomes or seed IDs.\n"
        "import base64 as _fourq_base64\n"
        "import json as _fourq_json\n"
        "import zlib as _fourq_zlib\n"
        "_CANDIDATE = kaggle_agent\n"
        f"_TAPE = _fourq_json.loads(_fourq_zlib.decompress(_fourq_base64.b85decode({payload!r})))\n"
        f"RETIRE_VARIANTS = {study.RETIRE_VARIANTS!r}\n"
        f"SKIP_HARVEST_VARIANTS = {study.SKIP_HARVEST_VARIANTS!r}\n"
        f"STRAWBERRY_CAP_VARIANTS = {study.STRAWBERRY_CAP_VARIANTS!r}\n\n"
        f"CONDITIONAL_CAP_VARIANTS = {study.CONDITIONAL_CAP_VARIANTS!r}\n\n"
        + inspect.getsource(study.eligible) + "\n"
        + inspect.getsource(study.wrap_candidate) + "\n"
        + "_FOURQ_STATS = {'activated': 0}\n"
        + f"_FOURQ_AGENT = wrap_candidate({args.variant!r}, 10000, _FOURQ_STATS)\n\n"
        # Kaggle selects the last *newly inserted* global callable. Remove the
        # captured old binding first so the new entry point is inserted last.
        + "globals().pop('kaggle_agent')\n\n"
        + "def kaggle_agent(observation, configuration=None):\n"
        + "    return _FOURQ_AGENT(observation)\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(base.rstrip() + overlay, encoding="utf-8")
    print(f"wrote {args.output}; embedded {len(tape)} tape steps")


if __name__ == "__main__":
    main()
