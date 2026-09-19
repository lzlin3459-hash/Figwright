#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pack a redistributable Figwright zip (source only; the user runs setup.cmd).

Excludes the local virtual environment and Python caches. The recipient
extracts the folder and double-clicks setup.cmd to build their own .venv.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
PARENT = PRODUCT_ROOT.parent
VERSION = "0.1.0"
# Distribution archive and its top-level folder use the public brand name,
# independent of the local working-copy directory name.
PKG_ROOT_NAME = "Figwright"
OUT_ZIP = PARENT / f"{PKG_ROOT_NAME}-v{VERSION}.zip"

EXCLUDE_DIR_NAMES = {
    ".venv",
    ".venv-origin",
    "venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".origin-smoke-out",
}
EXCLUDE_FILE_NAMES = {".origin-smoke.json"}
EXCLUDE_SUFFIXES = {".pyc"}


def should_skip(rel: Path) -> bool:
    # `rel` is the file path relative to PRODUCT_ROOT (caller already relativized it).
    if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
        return True
    if rel.name in EXCLUDE_FILE_NAMES:
        return True
    return rel.suffix in EXCLUDE_SUFFIXES


def main() -> int:
    files: list[Path] = []
    for path in PRODUCT_ROOT.rglob("*"):
        if path.is_file() and not should_skip(path.relative_to(PRODUCT_ROOT)):
            files.append(path)
    files.sort()

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            arcname = Path(PKG_ROOT_NAME) / path.relative_to(PRODUCT_ROOT)
            zf.write(path, arcname.as_posix())

    size_mb = OUT_ZIP.stat().st_size / 1024 / 1024
    print(f"packed {len(files)} files -> {OUT_ZIP} ({size_mb:.2f} MB)")
    must_have = ["LICENSE", "NOTICE", "README.md", "setup.cmd", "requirements.txt",
                 "figwright/cli.py", "figwright/origin_link.py",
                 "engine/templates/nmr/manifest.yaml",
                 "origin_runtime/README.md", "origin_runtime/requirements-origin.txt",
                 "origin_runtime/src/origin_sciplot/project_paths.py",
                 "origin_runtime/templates/nmr/manifest.yaml"]
    with zipfile.ZipFile(OUT_ZIP) as zf:
        names = set(zf.namelist())
        for rel in must_have:
            hit = f"{PKG_ROOT_NAME}/{rel}"
            print(("  OK  " if hit in names else "  MISSING ") + rel)
            assert hit in names, rel
        bad = [
            n
            for n in names
            if "/.venv/" in n
            or "/.venv-origin/" in n
            or "/.origin-smoke-out/" in n
            or n.endswith(".pyc")
            or n.endswith("/.origin-smoke.json")
        ]
        assert not bad, f"leaked excluded files: {bad[:5]}"
        # The optional backend ships source only: never bundle Origin binaries
        # or Learning/Trial watermarked smoke exports.
        forbidden_ext = (".exe", ".dll", ".pyd", ".opju", ".opj", ".tif")
        leaked_bin = [n for n in names if n.lower().endswith(forbidden_ext)]
        assert not leaked_bin, f"unexpected binary asset in package: {leaked_bin[:5]}"
    print("PACKAGE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
