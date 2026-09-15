#!/usr/bin/env python3
"""Build the optional pybind11 hot-path accelerators in-place."""
from __future__ import annotations

import platform
import shlex
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
MODULES = (
    (ROOT / "training" / "native_speedups_v2.cpp", ROOT / "training" / f"_kaggriculture_native{EXT}"),
    (ROOT / "training" / "native_reserve_v2.cpp", ROOT / "training" / f"_kaggriculture_reserve{EXT}"),
    (ROOT / "training" / "native_controller.cpp", ROOT / "training" / f"_kaggriculture_controller{EXT}"),
    (ROOT / "training" / "native_chassis.cpp", ROOT / "training" / f"_kaggriculture_chassis{EXT}"),
    (ROOT / "training" / "native_budget.cpp", ROOT / "training" / f"_kaggriculture_budget{EXT}"),
)


def _host_flags() -> list[str]:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return ["-march=native", "-mtune=native"]
    if machine in {"arm64", "aarch64"}:
        return ["-mcpu=native"]
    return []


def _prepared_source(src: Path, tmpdir: Path) -> Path:
    """Apply tiny pybind11-3.x compatibility rewrites without mutating the repo."""
    if src.name != "native_chassis.cpp":
        return src
    text = src.read_text(encoding="utf-8")
    text = text.replace(
        'invs=private_d.contains(py::str("inventories"))?py::cast<py::sequence>(private_d[py::str("inventories")]):py::list();',
        'invs=private_d.contains(py::str("inventories"))?py::cast<py::sequence>(private_d[py::str("inventories")]):py::cast<py::sequence>(py::list());',
    )
    text = text.replace(
        'tiles=farm.contains(py::str("tiles"))?py::cast<py::sequence>(farm[py::str("tiles")]):py::list();',
        'tiles=farm.contains(py::str("tiles"))?py::cast<py::sequence>(farm[py::str("tiles")]):py::cast<py::sequence>(py::list());',
    )
    text = text.replace(
        'hands=farm.contains(py::str("hands"))?py::cast<py::sequence>(farm[py::str("hands")]):py::list();',
        'hands=farm.contains(py::str("hands"))?py::cast<py::sequence>(farm[py::str("hands")]):py::cast<py::sequence>(py::list());',
    )
    prepared = tmpdir / src.name
    prepared.write_text(text, encoding="utf-8")
    return prepared


def main() -> None:
    includes = subprocess.check_output(
        [sys.executable, "-m", "pybind11", "--includes"], text=True
    ).strip()
    common = [
        "c++", "-O3", "-DNDEBUG", "-shared", "-std=c++17", "-fPIC",
        *_host_flags(), *shlex.split(includes),
    ]
    with tempfile.TemporaryDirectory(prefix="kag-native-build-") as td:
        tmpdir = Path(td)
        for src, out in MODULES:
            build_src = _prepared_source(src, tmpdir)
            cmd = [*common, str(build_src), "-o", str(out)]
            print(" ".join(shlex.quote(x) for x in cmd), flush=True)
            subprocess.run(cmd, check=True)
            print(out, flush=True)


if __name__ == "__main__":
    main()
