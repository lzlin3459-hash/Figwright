"""Render a confirmed table to watermark-free SVG/PNG/PDF via matplotlib."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless: no display required
import matplotlib.pyplot as plt  # noqa: E402

from . import env, selector

DEFAULT_FORMATS = ("png", "svg", "pdf")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_output_dir(source: Path) -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return source.resolve().parent / f"{source.stem}_Figwright_{stamp}"


def render(
    source: str | Path,
    *,
    template_id: str | None = None,
    intent: str | None = None,
    output_dir: str | Path | None = None,
    formats: tuple[str, ...] = DEFAULT_FORMATS,
    dpi: int = 300,
    strict: bool = False,
) -> dict[str, Any]:
    env.ensure_engine_on_path()
    from origin_sciplot.scientific_workflow import prepare_scientific

    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"找不到数据文件: {source}")

    chosen_selector: dict[str, Any] | None = None
    if not template_id:
        chosen_selector = selector.recommend(source, intent, limit=1)
        if not chosen_selector["recommendations"]:
            raise ValueError(
                "没有找到能渲染这张表的图种，请补充列名/单位或换用结构化更好的数据。"
            )
        template_id = chosen_selector["auto_selected"]

    prep = prepare_scientific(source, template_id)
    if strict and prep.requires_confirmation:
        return {
            "status": "needs_confirmation",
            "template_id": template_id,
            "reasons": list(prep.confirmation_reasons),
            "assignments": [[c, r] for c, r in prep.assignments],
        }

    from origin_sciplot.scientific_preview import _build_scientific_preview_figure

    target = Path(output_dir) if output_dir else _default_output_dir(source)
    target.mkdir(parents=True, exist_ok=True)

    figure = _build_scientific_preview_figure(prep)
    width_in, height_in = figure.get_size_inches()
    files: dict[str, str] = {}
    for ext in formats:
        ext = ext.lower()
        kwargs = {"dpi": dpi} if ext == "png" else {}
        out_path = target / f"result.{ext}"
        figure.savefig(out_path, format=ext, bbox_inches="tight", **kwargs)
        files[ext] = str(out_path)
    plt.close(figure)

    # Copy the source beside the outputs for a self-contained, traceable bundle.
    input_copy = target / source.name
    if not input_copy.exists():
        input_copy.write_bytes(source.read_bytes())

    report = {
        "schema_version": "1.0",
        "status": "ok",
        "backend": "matplotlib",
        "origin_required": False,
        "watermark": False,
        "editable_vector": "svg",
        "template_id": prep.template_id,
        "plot_kind": prep.plot_spec.plot_kind,
        "mapping_confidence": prep.confidence,
        "mapping_confirmed": prep.mapping_confirmed,
        "requires_confirmation": prep.requires_confirmation,
        "assignments": [[c, r] for c, r in prep.assignments],
        "warnings": list(prep.warnings),
        "source": {
            "file": source.name,
            "sha256": _sha256(source),
            "rows": prep.row_count,
            "columns": list(prep.source_columns),
            "format": prep.source_format,
        },
        "figure_size_inches": {"width": round(float(width_in), 3), "height": round(float(height_in), 3)},
        "plan_digest": prep.plan_digest,
        "output_dir": str(target),
        "files": files,
    }
    (target / "figwright_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if chosen_selector is not None:
        report["auto_selection"] = {
            "selected": chosen_selector["auto_selected"],
            "score": chosen_selector["auto_selection_score"],
            "margin": chosen_selector["auto_selection_margin"],
            "ambiguous": chosen_selector["auto_selection_ambiguous"],
            "candidate_count": chosen_selector["candidate_count"],
        }
        report["selection_ambiguous"] = chosen_selector["auto_selection_ambiguous"]
    return report
