#!/usr/bin/env python3
"""Write one-constant variants of a base agent for paired screening.

Each variant replaces exactly one top-level assignment line of the base file.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCREEN = {
    "V9_RACE_DEFAULT": ["36", "40", "48"],
    "V9_RACE_MARGIN": ["8", "16"],
    "V9_COURIER_FROM_HOUR": ["8", "16"],
    "V9_CARROT_RATIO": ["1.6", "2.5"],
    "V9_CARROT_WHEAT_RESERVE": ["25", "55"],
    "V9_HERD_MIN_WOOL": ["120", "180"],
    "V9_HERD_MIN_MILK": ["120", "180"],
    "V9_FERT_FIRST_DAY": ["10", "18"],
    "_FX_FLOW_MIN": ["6", "12"],
    "_EV_H": ["6", "12"],
    "_DP_H": ["6", "12"],
    "_MP_H": ["6", "12"],
    "_BD_MIN": ["4", "12"],
    "_BD_CAP": ["32", "96"],
    "_CXD_BUDGET": ["400", "1600"],
    "CROP_MIN_PRICE": ["60", "85"],
    "V13V_SKIP_DAYS": ["()", "(19, 21, 23, 25)"],
}


def set_constant(src: str, name: str, value: str) -> str:
    pattern = re.compile(rf"^({re.escape(name)}\s*=\s*)([^#\n]*?)(\s*(#.*)?)$", re.M)
    matches = pattern.findall(src)
    if len(matches) != 1:
        raise SystemExit(f"{name}: expected one assignment, found {len(matches)}")
    return pattern.sub(lambda m: m.group(1) + value + m.group(3), src, count=1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=str(ROOT / "test/results28_20260925/main.py"))
    p.add_argument("--out", default=str(ROOT / "candidates/r28var"))
    p.add_argument("--spec", help="JSON {name: [values]} or {variant: {name: value}}")
    a = p.parse_args()
    base = Path(a.base).read_text()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    manifest = {"base": {}}
    (out / "base.py").write_text(base)
    spec = json.loads(Path(a.spec).read_text()) if a.spec else SCREEN
    for key, val in spec.items():
        if isinstance(val, dict):  # combined variant
            src = base
            for n, v in val.items():
                src = set_constant(src, n, v)
            (out / f"{key}.py").write_text(src); manifest[key] = val
        else:
            for v in val:
                tag = f"{key.strip('_')}_{re.sub(r'[^0-9A-Za-z.]+', '_', v).strip('_') or 'empty'}"
                (out / f"{tag}.py").write_text(set_constant(base, key, v)); manifest[tag] = {key: v}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(len(manifest), "files in", out)


if __name__ == "__main__":
    main()
