#!/usr/bin/env python3
"""Build semantic ablations of the registered public v43 opponent."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def function_span(text: str, name: str) -> tuple[int, int]:
    node = next(
        node
        for node in ast.parse(text).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    lines = text.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: node.lineno - 1])
    end = sum(len(line) for line in lines[: node.end_lineno])
    return start, end


def replace_function(text: str, donor: str, name: str) -> str:
    start, end = function_span(text, name)
    donor_start, donor_end = function_span(donor, name)
    return text[:start] + donor[donor_start:donor_end] + text[end:]


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "test/public_v43_competitive_20260915/main.py",
    )
    parser.add_argument("--incumbent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source = args.source.read_text()
    incumbent = args.incumbent.read_text()
    variants = {"v43_full": source}
    variants["v43_no_overflow"] = source.replace(
        "_R148_OVERFLOW=True", "_R148_OVERFLOW=False", 1
    )
    variants["v43_old_router"] = replace_function(source, incumbent, "_router")
    old_timing = replace_function(source, incumbent, "_v219_request")
    variants["v43_old_timing"] = replace_function(
        old_timing, incumbent, "_v233_request"
    )
    reverted = replace_function(
        variants["v43_no_overflow"], incumbent, "_router"
    )
    reverted = replace_function(reverted, incumbent, "_v219_request")
    variants["v43_reverted_semantics"] = replace_function(
        reverted, incumbent, "_v233_request"
    )
    overlay_marker = "\n# Replay-derived invariants:"
    if overlay_marker not in incumbent:
        raise RuntimeError("incumbent survival/genome overlay marker is missing")
    incumbent_overlays = incumbent[incumbent.index(overlay_marker) :]
    variants["v43_plus_incumbent_overlays"] = (
        source.rstrip() + "\n" + incumbent_overlays
    )
    variants["incumbent"] = incumbent

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for name, text in variants.items():
        compile(text, f"{name}/main.py", "exec")
        folder = args.output_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "main.py").write_text(text)
        metadata[name] = {"sha256": digest(text)}
    (args.output_dir / "manifest.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )
    print(f"wrote {len(variants)} models to {args.output_dir}")


if __name__ == "__main__":
    main()
