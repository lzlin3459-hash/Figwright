"""FigFlow command-line interface (JSON to stdout)."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

import yaml

from . import __version__, env
from .render import DEFAULT_FORMATS, render
from .selector import recommend


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _error(code: str, message: str, *, status: int = 2) -> int:
    sys.stderr.write(
        json.dumps(
            {"ok": False, "error": {"code": code, "message": message}},
            ensure_ascii=False,
        )
        + "\n"
    )
    return status


def _cmd_doctor(_args: argparse.Namespace) -> int:
    deps = env.dependency_report()
    ready = env.engine_ok() and all(item["ok"] for item in deps)
    spec_dir_count = 0
    supported_count = 0
    if env.TEMPLATES_DIR.is_dir():
        spec_dir_count = sum(1 for p in env.TEMPLATES_DIR.iterdir() if p.is_dir())
    if ready:
        env.ensure_engine_on_path()
        from origin_sciplot.scientific_workflow import (
            SUPPORTED_SCIENTIFIC_TEMPLATE_IDS,
        )

        supported_count = len(SUPPORTED_SCIENTIFIC_TEMPLATE_IDS)
    _emit(
        {
            "schema_version": "1.0",
            "product": "FigFlow",
            "version": __version__,
            "ok": ready,
            "ready": ready,
            "backend": "matplotlib",
            "origin_required": False,
            "watermark": False,
            "python": platform.python_version(),
            "64bit": sys.maxsize > 2**32,
            "engine_home": str(env.ENGINE_ROOT),
            "template_spec_dirs": spec_dir_count,
            "supported_template_count": supported_count,
            "dependencies": deps,
        }
    )
    return 0


def _cmd_catalog(args: argparse.Namespace) -> int:
    if not env.engine_ok():
        return _error("engine_unavailable", "引擎缺失或依赖不完整，请先运行 setup/doctor。")
    env.ensure_engine_on_path()
    from origin_sciplot.scientific_workflow import (
        SUPPORTED_SCIENTIFIC_TEMPLATE_IDS,
    )

    drawable = set(SUPPORTED_SCIENTIFIC_TEMPLATE_IDS)
    rows = []
    for child in sorted(env.TEMPLATES_DIR.iterdir()):
        manifest_path = child / "manifest.yaml"
        if not manifest_path.is_file():
            continue
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        template_id = manifest.get("id", child.name)
        # Hide Origin-only routes (e.g. specialized XPS runners) this build cannot draw.
        if template_id not in drawable:
            continue
        if args.family and manifest.get("family") != args.family:
            continue
        rows.append(
            {
                "template_id": template_id,
                "name": manifest.get("name"),
                "family": manifest.get("family"),
                "category": manifest.get("category"),
                "description": manifest.get("description"),
            }
        )
    _emit({"schema_version": "1.0", "count": len(rows), "templates": rows})
    return 0


def _cmd_recommend(args: argparse.Namespace) -> int:
    if not env.engine_ok():
        return _error("engine_unavailable", "引擎缺失或依赖不完整，请先运行 setup/doctor。")
    payload = recommend(args.source, args.intent, limit=args.limit)
    _emit(payload)
    return 0


def _cmd_draw(args: argparse.Namespace) -> int:
    if not env.engine_ok():
        return _error("engine_unavailable", "引擎缺失或依赖不完整，请先运行 setup/doctor。")
    formats = tuple(f.strip() for f in args.formats.split(",") if f.strip())
    bad = [f for f in formats if f not in ("png", "svg", "pdf")]
    if bad:
        return _error("unsupported_format", f"仅支持 png/svg/pdf，收到: {bad}")
    try:
        result = render(
            args.source,
            template_id=args.template,
            intent=args.intent,
            output_dir=args.output_dir,
            formats=formats or DEFAULT_FORMATS,
            dpi=args.dpi,
            strict=args.strict,
        )
    except FileNotFoundError as exc:
        return _error("source_not_found", str(exc))
    except Exception as exc:  # noqa: BLE001
        return _error("render_failed", f"{type(exc).__name__}: {exc}")
    if result.get("status") == "needs_confirmation":
        _emit(result)
        return 3
    _emit(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="figflow", description="无水印 AI 科研绘图（本地、无需 Origin）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="检查环境与依赖")

    p_cat = sub.add_parser("catalog", help="列出支持的图种")
    p_cat.add_argument("--family")
    p_cat.set_defaults(func=_cmd_catalog)

    p_rec = sub.add_parser("recommend", help="分析表格并推荐图种")
    p_rec.add_argument("source")
    p_rec.add_argument("--intent", help="你的绘图目的（自然语言）")
    p_rec.add_argument("--limit", type=int, default=5)
    p_rec.set_defaults(func=_cmd_recommend)

    p_draw = sub.add_parser("draw", help="自动选图（或指定图种）并出图")
    p_draw.add_argument("source")
    p_draw.add_argument("--template", help="图种 id，不给则自动选择")
    p_draw.add_argument("--intent", help="你的绘图目的（自然语言）")
    p_draw.add_argument("--output-dir")
    p_draw.add_argument("--formats", default="png,svg,pdf")
    p_draw.add_argument("--dpi", type=int, default=300)
    p_draw.add_argument("--strict", action="store_true", help="列映射不确定时停下来等确认，不自动出图")
    p_draw.set_defaults(func=_cmd_draw)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _cmd_doctor(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
