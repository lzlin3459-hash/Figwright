#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FigFlow one-click bootstrap.

Creates a project-local virtual environment, installs the pinned open-source
dependencies, verifies the engine with `doctor`, and (when Doubao is present)
registers a local "figflow" Skill that points at this product folder.

Run through setup.cmd, which only exists to locate a suitable base Python.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = PRODUCT_ROOT / ".venv"
VENV_PY = VENV_DIR / "Scripts" / "python.exe"
REQUIREMENTS = PRODUCT_ROOT / "requirements.txt"
SKILL_SRC = PRODUCT_ROOT / "skill" / "figflow"

# Exit code that tells setup.cmd "this base interpreter is unsuitable, try the next".
WRONG_INTERPRETER = 40


def check_base_interpreter() -> None:
    if not (sys.version_info[:2] in [(3, 11), (3, 12)] and sys.maxsize > 2**32):
        print(
            f"[skip] 需要 64 位 Python 3.11 或 3.12，当前为 "
            f"{sys.version_info.major}.{sys.version_info.minor} "
            f"({'64' if sys.maxsize > 2**32 else '32'} 位)。",
            file=sys.stderr,
        )
        raise SystemExit(WRONG_INTERPRETER)


def run(cmd: list[str], *, quiet: bool = False) -> int:
    if not quiet:
        print(">", " ".join(str(c) for c in cmd))
    return subprocess.call([str(c) for c in cmd])


def create_venv(clean: bool) -> None:
    if clean and VENV_DIR.exists():
        import shutil

        shutil.rmtree(VENV_DIR)
    if VENV_PY.exists():
        print(f"[ok] 复用已有虚拟环境: {VENV_DIR}")
        return
    print(f"[1/3] 创建项目本地虚拟环境: {VENV_DIR}")
    builder = venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False)
    builder.create(str(VENV_DIR))
    if not VENV_PY.exists():
        raise SystemExit("虚拟环境创建失败，未找到 .venv\\Scripts\\python.exe")


def install_dependencies() -> None:
    print("[2/3] 安装锁定版本的开源依赖（仅需一次网络）...")
    code = run([VENV_PY, "-m", "pip", "install", "--upgrade", "pip"], quiet=True)
    if code != 0:
        raise SystemExit("pip 自升级失败，请检查网络后重试。")
    code = run([VENV_PY, "-m", "pip", "install", "-r", REQUIREMENTS])
    if code != 0:
        raise SystemExit("依赖安装失败，请检查网络或使用国内镜像后重试。")


def doctor() -> None:
    print("[3/3] 环境自检 doctor ...")
    code = run([VENV_PY, "-m", "figflow", "doctor"])
    if code != 0:
        raise SystemExit("doctor 未通过，请根据上面的提示排查。")


def _doubao_skill_dirs() -> list[Path]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return []
    base = Path(local) / "Doubao" / "User Data"
    if not base.is_dir():
        return []
    found = []
    for profile in base.glob("*"):
        target = profile / ".doubao" / "agent_mode" / "workspace" / ".user_skills"
        if target.is_dir():
            found.append(target)
    return found


def install_skill() -> bool:
    import shutil

    targets = _doubao_skill_dirs()
    if not targets:
        print("[skip] 未检测到豆包本地 Skill 目录；安装豆包后可重跑: setup.cmd install-skill")
        return False
    for skills_root in targets:
        dst = skills_root / "figflow"
        dst.mkdir(parents=True, exist_ok=True)
        # Skill instructions (UTF-8; read by Doubao, not by cmd).
        shutil.copyfile(SKILL_SRC / "SKILL.md", dst / "SKILL.md")
        # Pure-ASCII batch launcher plus its Unicode-safe Python bridge.
        shutil.copyfile(SKILL_SRC / "figflow.cmd.template", dst / "figflow.cmd")
        shutil.copyfile(SKILL_SRC / "_bootstrap.py", dst / "_bootstrap.py")
        # Absolute (possibly Chinese) paths live only in this UTF-8 JSON,
        # which the bridge reads with Python — never inside the .cmd.
        (dst / "figflow-home.json").write_text(
            json.dumps(
                {"product_home": str(PRODUCT_ROOT), "venv_python": str(VENV_PY)},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[ok] 已注册豆包 Skill: {dst}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="FigFlow setup")
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["all", "install-skill", "doctor"],
    )
    parser.add_argument("--clean", action="store_true", help="删除并重建 .venv")
    parser.add_argument(
        "--no-skill",
        action="store_true",
        help="只搭建本地环境，不注册豆包 Skill（命令行仍可用 figflow.cmd）",
    )
    args = parser.parse_args()

    if args.command == "doctor":
        check_base_interpreter()
        return run([VENV_PY, "-m", "figflow", "doctor"])

    if args.command == "install-skill":
        check_base_interpreter()
        if not VENV_PY.exists():
            raise SystemExit("尚未创建 .venv，请先运行 setup.cmd")
        install_skill()
        return 0

    check_base_interpreter()
    create_venv(args.clean)
    install_dependencies()
    doctor()
    skill_ok = False if args.no_skill else install_skill()
    print("\n=== FigFlow 安装完成 ===")
    print(f"产品目录 : {PRODUCT_ROOT}")
    print("直接使用 : FigFlow\\figflow.cmd doctor | catalog | recommend <文件> | draw <文件>")
    if args.no_skill:
        print("豆包指令 : 已按 --no-skill 跳过注册；稍后可运行 setup.cmd install-skill 补注册。")
    elif skill_ok:
        print("豆包指令 : 已注册，直接对豆包说“用 FigFlow 把这个数据画成图”即可。")
    else:
        print("豆包指令 : 装好豆包后运行 setup.cmd install-skill 即可一句话调用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
