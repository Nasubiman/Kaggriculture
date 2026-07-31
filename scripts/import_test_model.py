#!/usr/bin/env python3
"""Import a Kaggle submission archive into test/<name>/main.py."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tarfile


ROOT = Path(__file__).resolve().parents[1]
VALID_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_main(archive: Path) -> bytes:
    with tarfile.open(archive, "r:gz") as bundle:
        matches = [
            member
            for member in bundle.getmembers()
            if member.isfile() and member.name.lstrip("./") == "main.py"
        ]
        if len(matches) != 1:
            raise SystemExit(
                f"expected exactly one top-level main.py in {archive}, found {len(matches)}"
            )
        extracted = bundle.extractfile(matches[0])
        if extracted is None:
            raise SystemExit(f"could not read main.py from {archive}")
        return extracted.read()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="folder name below test/")
    parser.add_argument("--archive", type=Path, default=ROOT / "submission.tar.gz")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not VALID_NAME.fullmatch(args.name):
        raise SystemExit("name may contain only letters, numbers, dot, underscore, and dash")

    archive = args.archive.resolve()
    source = archive_main(archive)
    compile(source, f"{archive}:main.py", "exec")

    destination = args.models_dir.resolve() / args.name
    main_path = destination / "main.py"
    if destination.exists() and not args.force:
        raise SystemExit(f"model already exists: {destination} (use --force to replace it)")

    destination.mkdir(parents=True, exist_ok=True)
    main_path.write_bytes(source)
    metadata = {
        "name": args.name,
        "source_archive": archive.name,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": digest(archive.read_bytes()),
        "main_sha256": digest(source),
    }
    (destination / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"imported {args.name}: {main_path}")


if __name__ == "__main__":
    main()
