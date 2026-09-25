#!/usr/bin/env python3
"""Wrap one public replay KNN library with the proven route-repair chassis.

The result is a multi-file research candidate, not a Kaggle submission.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--template-dir", type=Path,
                        default=ROOT / "candidates" / "rank1_knn_255_pos4")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error(f"refusing to overwrite existing candidate: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    sources = {
        "library.npz": args.library_dir / "library.npz",
        "actions.zlib": args.library_dir / "actions.zlib",
        "metadata.json": args.library_dir / "metadata.json",
        "main.py": ROOT / "training" / "rank1_chassis_runtime.py",
        "rank1_knn.py": ROOT / "training" / "rank1_knn_runtime.py",
        "chassis.py": args.template_dir / "chassis.py",
        "settings.json": args.template_dir / "settings.json",
    }
    for name, source in sources.items():
        if not source.is_file():
            raise SystemExit(f"missing {source}")
        shutil.copyfile(source, args.output_dir / name)
    print(f"wrote research candidate {args.output_dir}")


if __name__ == "__main__":
    main()
