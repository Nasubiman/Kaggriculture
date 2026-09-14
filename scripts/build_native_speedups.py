#!/usr/bin/env python3
"""Build the optional pybind11 hot-path accelerators in-place."""
from __future__ import annotations

import platform
import shlex
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
MODULES = (
    (ROOT / "training" / "native_speedups_v2.cpp", ROOT / "training" / f"_kaggriculture_native{EXT}"),
    (ROOT / "training" / "native_reserve_v2.cpp", ROOT / "training" / f"_kaggriculture_reserve{EXT}"),
    (ROOT / "training" / "native_controller.cpp", ROOT / "training" / f"_kaggriculture_controller{EXT}"),
    (ROOT / "training" / "native_chassis.cpp", ROOT / "training" / f"_kaggriculture_chassis{EXT}"),
)


def _host_flags() -> list[str]:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return ["-march=native", "-mtune=native"]
    if machine in {"arm64", "aarch64"}:
        return ["-mcpu=native"]
    return []


def main() -> None:
    includes = subprocess.check_output(
        [sys.executable, "-m", "pybind11", "--includes"], text=True
    ).strip()
    common = [
        "c++", "-O3", "-DNDEBUG", "-shared", "-std=c++17", "-fPIC",
        *_host_flags(), *shlex.split(includes),
    ]
    for src, out in MODULES:
        cmd = [*common, str(src), "-o", str(out)]
        print(" ".join(shlex.quote(x) for x in cmd), flush=True)
        subprocess.run(cmd, check=True)
        print(out, flush=True)


if __name__ == "__main__":
    main()
