#!/usr/bin/env python3
"""Build v4 native extensions only when their sources or ABI changed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig


ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training"
STAMP = TRAINING / ".native_speedups_v4.json"
MODULES = (
    "_kaggriculture_native",
    "_kaggriculture_reserve",
    "_kaggriculture_controller",
    "_kaggriculture_chassis",
    "_kaggriculture_budget",
    "_kaggriculture_input",
    "_kaggriculture_sales",
    "_kaggriculture_service",
    "_kaggriculture_simulator",
)


def inputs() -> list[Path]:
    native = [
        path
        for path in TRAINING.glob("native_*")
        if path.suffix in {".cpp", ".hpp"}
    ]
    builders = [
        ROOT / "scripts" / name
        for name in (
            "build_native_speedups.py",
            "build_native_speedups_turbo.py",
            "build_native_speedups_policy.py",
            "prepare_native_simulator_source.py",
        )
    ]
    return sorted(native + builders)


def fingerprint() -> str:
    digest = hashlib.sha256()
    digest.update(sys.implementation.cache_tag.encode())
    digest.update(sysconfig.get_platform().encode())
    for path in inputs():
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def outputs() -> list[Path]:
    extension = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    return [TRAINING / f"{name}{extension}" for name in MODULES]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    subprocess.run(
        [sys.executable, str(ROOT / "scripts/prepare_native_simulator_source.py")],
        check=True,
    )
    wanted = fingerprint()
    current = json.loads(STAMP.read_text()) if STAMP.exists() else {}
    built = outputs()
    if not args.force and current.get("fingerprint") == wanted and all(
        path.is_file() for path in built
    ):
        print("v4 native extensions are current")
        return

    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_native_speedups_policy.py")],
        check=True,
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TRAINING)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import agent_runtime; "
            "import experimental_fast_kaggriculture_v3; "
            "assert agent_runtime.native_acceleration_available()",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    STAMP.write_text(
        json.dumps(
            {
                "fingerprint": wanted,
                "python": sys.version,
                "platform": sysconfig.get_platform(),
                "outputs": [path.name for path in built],
            },
            indent=2,
        )
        + "\n"
    )
    print("built v4 native extensions")


if __name__ == "__main__":
    main()
