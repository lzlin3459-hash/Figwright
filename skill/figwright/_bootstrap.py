#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ASCII-safe bridge installed into the Doubao Skill folder.

The Skill directory itself lives under an ASCII path, but the Figwright product
and its venv may sit in a path containing Chinese characters. A batch file
stores such a path as raw bytes and breaks on GBK/936 machines. So the .cmd
launcher stays pure-ASCII and only invokes this file with the ``py`` launcher;
this bridge reads the UTF-8 config and starts the real venv interpreter via
CreateProcessW (fully Unicode-safe).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    cfg_path = Path(__file__).resolve().with_name("figwright-home.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    venv_python = cfg["venv_python"]
    product_home = cfg["product_home"]

    if not Path(venv_python).is_file():
        sys.stderr.write(
            f"[Figwright] venv python not found: {venv_python}\n"
            "Please run setup.cmd in the Figwright folder again.\n"
        )
        return 2

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = product_home + os.pathsep + env.get("PYTHONPATH", "")

    completed = subprocess.run(
        [venv_python, "-m", "figwright", *sys.argv[1:]],
        env=env,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
