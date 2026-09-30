#!/usr/bin/env python3
"""Replace one shop-pair route in an existing embedded multi-pair submission."""

from __future__ import annotations

import argparse
import ast
import base64
import zlib
from pathlib import Path

from kaggle_environments.agent import get_last_callable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--secondary", type=Path, required=True)
    parser.add_argument("--shops", nargs=2, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    text = args.source.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    assignments = ("_MPH_SOURCES", "_MPH_ENTRIES", "_MPH_PAIRS")
    positions = {}
    values = {}
    for name in assignments:
        found = [(index, line) for index, line in enumerate(lines)
                 if line.startswith(name + " = ")]
        if len(found) != 1:
            parser.error(f"expected exactly one {name} assignment")
        positions[name], line = found[0]
        values[name] = ast.literal_eval(line.split("=", 1)[1].strip())
    source = args.secondary.read_text(encoding="utf-8")
    key = "s" + str(len(values["_MPH_SOURCES"]))
    if key in values["_MPH_SOURCES"]:
        parser.error(f"duplicate source key: {key}")
    values["_MPH_SOURCES"][key] = base64.b64encode(zlib.compress(source.encode(), 9)).decode()
    values["_MPH_ENTRIES"][key] = get_last_callable(source, path=str(args.secondary)).__name__
    values["_MPH_PAIRS"][tuple(args.shops)] = key
    for name in assignments:
        lines[positions[name]] = f"{name} = {values[name]!r}\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(lines), encoding="utf-8")
    print(f"wrote {args.output}: {tuple(args.shops)} -> {key}")


if __name__ == "__main__":
    main()
