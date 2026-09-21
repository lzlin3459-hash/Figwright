"""Figwright command-line interface (JSON to stdout)."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import yaml

from . import __version__, env, origin_link
from .render import DEFAULT_FORMATS, MAX_DPI, MIN_DPI, render
from .selector import recommend


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _error(code: str, message: str, *, status: int = 2, extra: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    if extra:
        payload["error"].update(extra)
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return status


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _origin_progress(ev: dict[str, Any]) -> None:
    kind = ev.get("type")
    if kind == "progress":
        sys.stderr.write(f"[origin] {ev.get('step')}: {ev.get('message', '')}\n")
    elif kind == "warning":
        sys.stderr.write(f"[origin][warn] {ev.get('message', '')}\n")
    sys.stderr.flush()


def _origin_doctor_section() -> dict[str, Any]:
    section: dict[str, Any] = {
        "optional_backend": "origin",
        "maturity": "experimental",
        "shipped": origin_link.runtime_files_present(),
    }
    if not section["shipped"]:
        return section
    section["environment"] = origin_link.origin_env_report()
    section["com_registered"] = origin_link.detect_com_registration()
    cache = origin_link.load_smoke_cache()
    if cache:
        section["last_smoke"] = {
            "status": cache.get("status"),
            "checked_at": cache.get("checked_at"),
        }
    return section


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
            "product": "Figwright",
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
            "origin_backend": _origin_doctor_section(),
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


def _resolve_template_for_origin(source: Path, args: argparse.Namespace) -> tuple[str | None, int]:
    """Pick a template for the Origin backend using the main-line selector."""

    if args.template:
        return args.template, 0
    chosen = recommend(source, args.intent, limit=1)
    if not chosen.get("recommendations"):
        return None, _error(
            "no_renderable_template",
            "没有找到能渲染这张表的图种，请补充列名/单位或用 --template 明确指定。",
        )
    if chosen.get("auto_selection_ambiguous"):
        _emit(
            {
                "status": "needs_confirmation",
                "backend": "origin",
                "auto_selected": chosen.get("auto_selected"),
                "candidates": [
                    r.get("template_id") for r in chosen.get("recommendations", [])[:3]
                ],
                "message": "自动选图存在歧义，请用 --template 指定图种后再用 Origin 后端出图。",
            }
        )
        return None, 3
    return chosen["auto_selected"], 0


def _cmd_draw_origin(args: argparse.Namespace, source: Path, formats: tuple[str, ...]) -> int:
    if not origin_link.runtime_files_present():
        return _error(
            "origin_backend_not_shipped",
            "本发行包未包含可选 Origin 后端文件。",
        )
    if not origin_link.origin_venv_installed():
        return _error(
            "origin_backend_not_installed",
            "可选 Origin 后端尚未安装。请先运行: setup.cmd --with-origin",
            status=origin_link.RC_USAGE,
        )
    if not args.confirm_licensed_origin:
        return _error(
            "origin_license_confirmation_required",
            "使用 --backend origin 前请确认本机已安装并激活正版 Origin/OriginPro 2021+，"
            "并追加 --confirm-licensed-origin。学习/试用版会带 demo 水印且无法保存工程；"
            "Figwright 不提供任何去除水印或绕过授权的手段，无水印请直接用默认 matplotlib 后端。",
            status=origin_link.RC_LICENSE_CONFIRMATION,
        )

    # License gate runs BEFORE chart selection so a Learning/Trial machine is
    # rejected with the licensing reason rather than a chart-ambiguity code.
    # Behavioral gate: a real non-empty .opju must be saveable (smoke=passed).
    cache = origin_link.load_smoke_cache()
    cache_status = cache.get("status") if cache else None
    if cache_status == "degraded":
        checked = cache.get("checked_at", "未知时间") if cache else "未知时间"
        return _error(
            "origin_license_limited",
            f"最近一次自检（{checked}）为 degraded：当前 Origin 无法保存可编辑工程（典型为学习/试用版），"
            "图片导出可能带 demo 水印。已停止，未生成正式产物。Figwright 不去除水印；"
            "请改用默认 `figwright draw`（matplotlib）获得无水印图，或在已激活正版 Origin 的电脑上"
            "重新运行 figwright origin-smoke 后再用 --backend origin。",
            status=origin_link.RC_ORIGIN_LIMITED,
            extra={"smoke_status": "degraded"},
        )
    if cache_status != "passed":
        sys.stderr.write("[origin] 首次使用，正在做 Origin 连通性与工程保存自检（不修改你的数据）...\n")
        try:
            smoke = origin_link.run_smoke(on_event=_origin_progress)
        except origin_link.OriginBackendError as exc:
            return _error(
                exc.code,
                exc.message,
                status=origin_link.RC_ORIGIN_TECHNICAL,
                extra={"stage": exc.stage} if exc.stage else None,
            )
        smoke_status = smoke.get("status")
        if smoke_status == "degraded":
            return _error(
                "origin_license_limited",
                "自检结果为 degraded：当前 Origin 无法保存可编辑工程（典型为学习/试用版），"
                "图片导出可能带 demo 水印。已停止，未生成正式产物。Figwright 不去除水印；"
                "请改用默认 `figwright draw`（matplotlib）获得无水印图，或在已激活正版 Origin 的电脑上使用。",
                status=origin_link.RC_ORIGIN_LIMITED,
                extra={"smoke_status": "degraded"},
            )
        if smoke_status != "passed":
            return _error(
                "origin_smoke_inconclusive",
                f"自检状态异常: {smoke_status}",
                status=origin_link.RC_ORIGIN_TECHNICAL,
            )
    else:
        smoke_status = "passed"

    template_id, rc = _resolve_template_for_origin(source, args)
    if template_id is None:
        return rc

    target = Path(args.output_dir) if args.output_dir else (
        source.resolve().parent / f"{source.stem}_Figwright-Origin_{_timestamp()}"
    )
    try:
        origin_link.run_render(
            source,
            template_id,
            target,
            keep_open=args.keep_origin_open,
            on_event=_origin_progress,
        )
    except origin_link.OriginBackendError as exc:
        return _error(
            exc.code,
            exc.message,
            status=origin_link.RC_ORIGIN_TECHNICAL,
            extra={"stage": exc.stage} if exc.stage else None,
        )

    artifacts = origin_link.collect_origin_artifacts(target)
    if not artifacts["has_opju"]:
        return _error(
            "origin_opju_missing",
            "自检通过但未在输出目录找到非空 result.opju，已按失败处理（fail-closed）。",
            status=origin_link.RC_ORIGIN_TECHNICAL,
        )

    input_copy = target / source.name
    if not input_copy.exists():
        input_copy.write_bytes(source.read_bytes())

    result = {
        "schema_version": "1.0",
        "status": "ok",
        "backend": "origin",
        "maturity": "experimental",
        "origin_required": True,
        "smoke_status": smoke_status,
        "editable_opju": True,
        "template_id": template_id,
        "output_dir": str(target),
        "files": artifacts["files"],
        "bytes": artifacts["bytes"],
        "origin_verify_report": artifacts["verify_report"],
        "note": "已确认为可保存工程的 Origin 环境；成品以你本机正版授权为准。",
        "source": {"file": source.name, "sha256": _sha256(source)},
    }
    (target / "figwright_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _emit(result)
    return 0


def _timestamp() -> str:
    import datetime as _dt

    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _cmd_origin_smoke(args: argparse.Namespace) -> int:
    if not origin_link.runtime_files_present():
        return _error("origin_backend_not_shipped", "本发行包未包含可选 Origin 后端文件。")
    if not origin_link.origin_venv_installed():
        return _error(
            "origin_backend_not_installed",
            "可选 Origin 后端尚未安装。请先运行: setup.cmd --with-origin",
            status=origin_link.RC_USAGE,
        )
    try:
        report = origin_link.run_smoke(
            args.output_dir, keep_open=args.keep_origin_open, on_event=_origin_progress
        )
    except origin_link.OriginBackendError as exc:
        return _error(
            exc.code,
            exc.message,
            status=origin_link.RC_ORIGIN_TECHNICAL,
            extra={"stage": exc.stage} if exc.stage else None,
        )
    status = report.get("status")
    report["maturity"] = "experimental"
    report["interpretation"] = (
        "正版环境，可保存可编辑工程 result.opju。"
        if status == "passed"
        else "学习/试用或项目保存受限环境：无法生成正式 .opju，请用默认 matplotlib 后端获取无水印图。"
    )
    _emit(report)
    return 0


def _cmd_draw(args: argparse.Namespace) -> int:
    if not (MIN_DPI <= args.dpi <= MAX_DPI):
        return _error(
            "invalid_dpi",
            f"--dpi 需为 {MIN_DPI}–{MAX_DPI} 之间的整数（常用 300，高质量线稿可用 600）；收到 {args.dpi}。",
        )
    if not env.engine_ok():
        return _error("engine_unavailable", "引擎缺失或依赖不完整，请先运行 setup/doctor。")
    formats = tuple(f.strip() for f in args.formats.split(",") if f.strip())
    bad = [f for f in formats if f not in ("png", "svg", "pdf")]
    if bad:
        return _error("unsupported_format", f"仅支持 png/svg/pdf，收到: {bad}")
    source = Path(args.source)
    if not source.is_file():
        return _error("source_not_found", f"找不到数据文件: {source}")

    if args.backend == "origin":
        return _cmd_draw_origin(args, source, formats or DEFAULT_FORMATS)

    try:
        result = render(
            source,
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
    parser = argparse.ArgumentParser(prog="figwright", description="无水印 AI 科研绘图（本地、无需 Origin）")
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
    p_draw.add_argument(
        "--backend",
        choices=["matplotlib", "origin"],
        default="matplotlib",
        help="绘图后端：matplotlib（默认，无水印）或 origin（实验性可选，需正版 Origin）",
    )
    p_draw.add_argument(
        "--confirm-licensed-origin",
        action="store_true",
        help="声明本机已安装并激活正版 Origin/OriginPro（使用 --backend origin 时必填）",
    )
    p_draw.add_argument(
        "--keep-origin-open",
        action="store_true",
        help="（调试）完成后保留 Origin 窗口，默认自动关闭",
    )
    p_draw.set_defaults(func=_cmd_draw)

    p_smoke = sub.add_parser(
        "origin-smoke", help="（可选后端）预检本机 Origin 能否连接并保存工程"
    )
    p_smoke.add_argument("--output-dir")
    p_smoke.add_argument("--keep-origin-open", action="store_true")
    p_smoke.set_defaults(func=_cmd_origin_smoke)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _cmd_doctor(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
