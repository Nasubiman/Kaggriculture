#!/usr/bin/env python3
"""Build an isolated research candidate joining FQ imitation to current main."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-dir", type=Path, required=True)
    parser.add_argument("--incumbent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--switch-step", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.switch_step <= 719:
        parser.error("switch-step must be in 1..719")
    if args.output_dir.exists():
        parser.error(f"refusing to overwrite existing candidate: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    files = {
        "library.npz": args.library_dir / "library.npz",
        "actions.zlib": args.library_dir / "actions.zlib",
        "metadata.json": args.library_dir / "metadata.json",
        "settings.json": args.library_dir / "settings.json",
        "rank1_knn.py": ROOT / "training" / "rank1_knn_runtime.py",
        "incumbent.py": args.incumbent,
        "main.py": ROOT / "training" / "fq_knn_hybrid_runtime.py",
    }
    for name, source in files.items():
        if not source.is_file():
            raise SystemExit(f"missing {source}")
        shutil.copyfile(source, args.output_dir / name)
    (args.output_dir / "hybrid_settings.json").write_text(
        json.dumps({"switch_step": args.switch_step}, indent=2) + "\n")
    print(f"wrote research candidate {args.output_dir}")


if __name__ == "__main__":
    main()
