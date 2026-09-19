#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pack a redistributable FigFlow zip (source only; the user runs setup.cmd).

Excludes the local virtual environment and Python caches. The recipient
extracts the folder and double-clicks setup.cmd to build their own .venv.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
PARENT = PRODUCT_ROOT.parent
VERSION = "0.1.0"
OUT_ZIP = PARENT / f"FigFlow-v{VERSION}.zip"

EXCLUDE_DIR_NAMES = {".venv", "venv", "__pycache__", ".git", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc"}


def should_skip(path: Path) -> bool:
    if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
        return True
    return path.suffix in EXCLUDE_SUFFIXES


def main() -> int:
    files: list[Path] = []
    for path in PRODUCT_ROOT.rglob("*"):
        if path.is_file() and not should_skip(path.relative_to(PRODUCT_ROOT)):
            files.append(path)
    files.sort()

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            arcname = Path(PRODUCT_ROOT.name) / path.relative_to(PRODUCT_ROOT)
            zf.write(path, arcname.as_posix())

    size_mb = OUT_ZIP.stat().st_size / 1024 / 1024
    print(f"packed {len(files)} files -> {OUT_ZIP} ({size_mb:.2f} MB)")
    must_have = ["LICENSE", "NOTICE", "README.md", "setup.cmd", "requirements.txt",
                 "figflow/cli.py", "engine/templates/nmr/manifest.yaml"]
    with zipfile.ZipFile(OUT_ZIP) as zf:
        names = set(zf.namelist())
        for rel in must_have:
            hit = f"{PRODUCT_ROOT.name}/{rel}"
            print(("  OK  " if hit in names else "  MISSING ") + rel)
            assert hit in names, rel
        bad = [n for n in names if "/.venv/" in n or n.endswith(".pyc")]
        assert not bad, f"leaked excluded files: {bad[:3]}"
    print("PACKAGE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
