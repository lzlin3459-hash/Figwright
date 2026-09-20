#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pack a redistributable Figwright zip (source only; the user runs setup.cmd).

Excludes the local virtual environment and Python caches. The recipient
extracts the folder and double-clicks setup.cmd to build their own .venv.

Windows batch launchers are normalized to CRLF while writing the archive,
regardless of the working copy's line endings or git: a multi-line
``for ... do (`` block with bare LF line endings can fail to parse in
cmd.exe and makes a double-clicked setup.cmd appear to "do nothing".
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
EXCLUDE_FILE_NAMES = {".origin-smoke.json", "setup-log.txt"}
EXCLUDE_SUFFIXES = {".pyc"}
BATCH_SUFFIXES = (".cmd", ".bat")


def should_skip(rel: Path) -> bool:
    # `rel` is the file path relative to PRODUCT_ROOT (caller already relativized it).
    if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
        return True
    if rel.name in EXCLUDE_FILE_NAMES:
        return True
    return rel.suffix in EXCLUDE_SUFFIXES


def is_batch(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(BATCH_SUFFIXES) or name.endswith(".cmd.template")


def to_crlf(data: bytes) -> bytes:
    text = data.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    return text.encode("utf-8")


def main() -> int:
    files: list[Path] = []
    for path in PRODUCT_ROOT.rglob("*"):
        if path.is_file() and not should_skip(path.relative_to(PRODUCT_ROOT)):
            files.append(path)
    files.sort()

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            arcname = (Path(PKG_ROOT_NAME) / path.relative_to(PRODUCT_ROOT)).as_posix()
            if is_batch(path):
                # Guarantee Windows-correct line endings inside the archive.
                zf.writestr(arcname, to_crlf(path.read_bytes()))
            else:
                zf.write(path, arcname)

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
            or n.endswith("/setup-log.txt")
        ]
        assert not bad, f"leaked excluded files: {bad[:5]}"
        # The optional backend ships source only: never bundle Origin binaries
        # or Learning/Trial watermarked smoke exports.
        forbidden_ext = (".exe", ".dll", ".pyd", ".opju", ".opj", ".tif")
        leaked_bin = [n for n in names if n.lower().endswith(forbidden_ext)]
        assert not leaked_bin, f"unexpected binary asset in package: {leaked_bin[:5]}"
        # Every Windows launcher inside the archive must be pure CRLF.
        batch = [
            n for n in names
            if n.lower().endswith(BATCH_SUFFIXES) or n.endswith(".cmd.template")
        ]
        assert batch, "no Windows batch launcher found in package"
        for n in batch:
            b = zf.read(n)
            assert b"\r\n" in b, f"batch without CRLF: {n}"
            assert b.count(b"\n") == b.count(b"\r\n"), f"bare LF in batch: {n}"
        print(f"  OK   {len(batch)} batch launchers verified CRLF")
    print("PACKAGE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
