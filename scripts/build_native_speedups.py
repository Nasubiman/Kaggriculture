#!/usr/bin/env python3
"""Build the optional pybind11 hot-path accelerator in-place."""
from __future__ import annotations

import shlex
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "training" / "native_speedups.cpp"
EXT = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
OUT = ROOT / "training" / f"_kaggriculture_native{EXT}"


def main() -> None:
    includes = subprocess.check_output(
        [sys.executable, "-m", "pybind11", "--includes"], text=True
    ).strip()
    cmd = [
        "c++", "-O3", "-DNDEBUG", "-shared", "-std=c++17", "-fPIC",
        *shlex.split(includes), str(SRC), "-o", str(OUT),
    ]
    print(" ".join(shlex.quote(x) for x in cmd), flush=True)
    subprocess.run(cmd, check=True)
    print(OUT, flush=True)


if __name__ == "__main__":
    main()
