#!/usr/bin/env python3
"""Tune one embedded agent's scalar only after a chosen shop pair is revealed."""

from __future__ import annotations

import argparse
import ast
import base64
import zlib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--value", type=float, required=True)
    parser.add_argument("--shops", nargs=2, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lines = args.source.read_text(encoding="utf-8").splitlines(keepends=True)
    source_line = next((i for i, line in enumerate(lines)
                        if line.startswith("_MPH_SOURCES = ")), None)
    entry_line = next((i for i, line in enumerate(lines)
                       if line.startswith("_MPH_ENTRIES = ")), None)
    if source_line is None or entry_line is None:
        parser.error("source is not an embedded multi-pair submission")
    sources = ast.literal_eval(lines[source_line].split("=", 1)[1].strip())
    entries = ast.literal_eval(lines[entry_line].split("=", 1)[1].strip())
    if args.key not in sources:
        parser.error(f"missing source {args.key}")
    original = zlib.decompress(base64.b64decode(sources[args.key])).decode()
    anchor = f"{args.parameter} = "
    if not any(line.startswith(anchor) for line in original.splitlines()):
        parser.error(f"missing top-level parameter {args.parameter}")
    entry = entries[args.key]
    wrapper = f'''

# Shop-pair-only scalar adjustment. The source strategy and routing stay intact.
_PAIR_TUNE_PARENT = {entry}
_PAIR_TUNE_SHOPS = {tuple(args.shops)!r}

def _pair_tuned_agent(observation, configuration=None):
    global {args.parameter}
    step = int(observation.get("step", 0))
    shops = tuple((observation.get("town") or {{}}).get("unlocked_shops", [])[:2])
    {args.parameter} = {args.value!r} if step >= 144 and shops == _PAIR_TUNE_SHOPS else {args.parameter}_ORIGINAL
    return _PAIR_TUNE_PARENT(observation, configuration)

{args.parameter}_ORIGINAL = {args.parameter}
'''
    revised = original + wrapper
    sources[args.key] = base64.b64encode(zlib.compress(revised.encode(), 9)).decode()
    entries[args.key] = "_pair_tuned_agent"
    lines[source_line] = f"_MPH_SOURCES = {sources!r}\n"
    lines[entry_line] = f"_MPH_ENTRIES = {entries!r}\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(lines), encoding="utf-8")
    print(f"wrote {args.output}: {args.key} {args.parameter}={args.value} for {tuple(args.shops)}")


if __name__ == "__main__":
    main()
