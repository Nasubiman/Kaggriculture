#!/usr/bin/env python3
"""Align the native r36 reserve activation window with the Python policy."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "training" / "native_reserve_v2.cpp"
text = path.read_text()
old = 'if(step<216||step>=696)return py::make_tuple(0,0);'
new = 'if(step<288||step>=696)return py::make_tuple(0,0);'
if old not in text:
    if new in text:
        print("native reserve start already aligned")
        raise SystemExit(0)
    raise SystemExit("native reserve start pattern not found")
path.write_text(text.replace(old, new, 1))
print("aligned native reserve start: 216 -> 288")
