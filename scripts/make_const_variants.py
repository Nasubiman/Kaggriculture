#!/usr/bin/env python3
"""Write single-file variants of a base agent with top-level constants replaced.

Each spec is NAME=CONST:VALUE[;CONST:VALUE...]. A constant must be assigned
exactly once at the top level of the base file (checked).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("specs", nargs="+")
    a = ap.parse_args()
    src = Path(a.base).read_text()
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    for spec in a.specs:
        name, body = spec.split("=", 1)
        text = src
        for part in body.split(";"):
            const, value = part.split(":", 1)
            pat = re.compile(rf"^{re.escape(const)}\s*=.*$", re.M)
            hits = pat.findall(text)
            if len(hits) != 1:
                raise SystemExit(f"{const}: {len(hits)} top-level assignments")
            text = pat.sub(f"{const} = {value}", text)
        (out / f"{name}.py").write_text(text)
        print("wrote", out / f"{name}.py")


if __name__ == "__main__":
    main()
