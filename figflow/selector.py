"""Deterministic auto chart selection over the bundled template library.

The heavy lifting (column role inference, per-template mapping, confidence)
comes from the engine's ``prepare_scientific``. This module ranks every
template that can actually render the user's table, optionally boosting
templates whose metadata or bilingual synonyms match the user's
natural-language intent.

The conversational AI (Doubao) presents and confirms the choice; this module
only produces auditable, reproducible candidates.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from . import env

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+")

# Bilingual intent keywords beyond what the manifests already contain.
# ASCII keywords shorter than 3 chars (common spectroscopy abbreviations) are
# matched by exact token equality to avoid false hits inside longer words.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "bar": ("bar", "bars", "柱状图", "柱状", "柱形图", "分组柱"),
    "horizontal_bar": ("horizontal bar", "条形图", "横向条形", "横条图"),
    "stacked_bar": ("stacked bar", "堆积柱", "堆叠柱", "堆积条形图", "堆叠条形图"),
    "percent_stacked_bar": ("percent stacked", "百分比堆积", "百分比堆叠", "百分比柱", "占比柱"),
    "line_error": ("error bar", "误差线", "误差棒", "带误差折线"),
    "trend": ("trend", "line chart", "折线图", "折线", "趋势图", "线图"),
    "scatter": ("scatter", "散点图", "散点", "相关性图"),
    "bubble": ("bubble", "气泡图", "气泡"),
    "histogram": ("histogram", "直方图", "柱状分布", "频数分布"),
    "violin": ("violin", "小提琴图", "小提琴"),
    "raincloud": ("raincloud", "雨云图", "雨云"),
    "grouped_box": ("boxplot", "box plot", "箱线图", "箱型图", "盒须图", "箱图"),
    "raw_summary": ("raw points", "原始点", "数据点汇总", "原始分布点"),
    "pie": ("pie", "pie chart", "饼图", "饼状图"),
    "sankey": ("sankey", "桑基图", "流向图"),
    "radar": ("radar", "雷达图", "蜘蛛图"),
    "circular_network": ("network", "关系网络", "网络图", "节点关系"),
    "forest": ("forest plot", "森林图"),
    "heatmap": ("heatmap", "热图", "热力图", "颜色矩阵"),
    "density_ridgeline3d": ("ridgeline", "山脊图", "密度脊", "3d密度"),
    "trajectory3d": ("3d trajectory", "三维轨迹", "3d轨迹", "相空间轨迹"),
    "paired_trajectory": ("paired", "配对", "前后对比连线", "配对轨迹"),
    "bland_altman": ("bland altman", "bland-altman", "一致性分析"),
    "calibration_curve": ("calibration", "校准曲线", "校准图"),
    "decision_curve": ("decision curve", "dca", "决策曲线"),
    "diagnostic_curve": ("roc", "auc", "诊断曲线", "受试者工作特征"),
    "confusion_matrix": ("confusion", "混淆矩阵", "分类矩阵"),
    "shap_summary": ("shap", "特征贡献", "模型解释", "可解释性"),
    "shap_dashboard": ("shap dashboard", "shap面板", "特征重要性面板"),
    "cv": ("cyclic voltammetry", "循环伏安", "伏安曲线"),
    "lsv": ("lsv", "线性扫描", "极化曲线", "线性伏安"),
    "eis": ("eis", "impedance", "阻抗", "奈奎斯特", "nyquist", "电化学阻抗"),
    "dsc": ("dsc", "差示扫描", "热分析", "热流曲线", "量热"),
    "ftir": ("ftir", "红外光谱", "红外", "傅里叶红外"),
    "nmr": ("nmr", "核磁", "核磁共振", "化学位移", "波谱"),
    "pl": ("photoluminescence", "光致发光", "荧光光谱", "荧光曲线"),
    "uv_vis": ("ultraviolet", "uv-vis", "uv vis", "紫外可见", "紫外", "吸收光谱"),
    "xas": ("xas", "xanes", "exafs", "x射线吸收"),
    "xps_compare": ("xps", "光电子能谱", "x射线光电子", "x-ray photoelectron", "光电子"),
    "xrd": ("xrd", "x射线衍射", "衍射图谱", "衍射", "rietveld", "物相分析", "x ray diffraction"),
}


def _load_manifest(template_id: str) -> dict[str, Any]:
    path = env.TEMPLATES_DIR / template_id / "manifest.yaml"
    if not path.is_file():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


def _searchable_text(manifest: dict[str, Any]) -> str:
    guide = manifest.get("data_guide") or {}
    parts: list[str] = [
        str(manifest.get("id", "")),
        str(manifest.get("name", "")),
        str(manifest.get("category", "")),
        str(manifest.get("family", "")),
        str(manifest.get("description", "")),
        str(guide.get("headline_zh", "")),
    ]
    for list_key in ("aliases", "required_columns", "accepted_layouts", "notes_zh"):
        value = guide.get(list_key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    for example in manifest.get("examples") or []:
        parts.append(str(example.get("name_zh", "")))
        parts.append(str(example.get("description_zh", "")))
    return " ".join(parts).lower()


def _ascii_tokens(intent_lower: str) -> list[str]:
    return [tok for tok in _TOKEN_RE.findall(intent_lower) if tok.isascii()]


def _keyword_hits(keywords: list[str], intent_lower: str, ascii_tokens: list[str]) -> list[str]:
    hits: list[str] = []
    for raw in keywords:
        kw = raw.strip().lower()
        if not kw:
            continue
        if kw.isascii():
            if len(kw) <= 2:
                matched = kw in ascii_tokens
            else:
                matched = any(
                    kw in tok or (len(tok) >= 3 and tok in kw) for tok in ascii_tokens
                )
        else:  # CJK: substring match against the whole sentence
            matched = kw in intent_lower
        if matched and raw not in hits:
            hits.append(raw)
    return hits


def _intent_boost(
    intent: str | None, text: str, template_id: str
) -> tuple[float, list[str]]:
    if not intent:
        return 0.0, []
    intent_lower = intent.lower()
    ascii_tokens = _ascii_tokens(intent_lower)
    keywords = [tok for tok in _TOKEN_RE.findall(text) if len(tok) >= 2]
    keywords.extend(SYNONYMS.get(template_id, ()))
    hits = _keyword_hits(keywords, intent_lower, ascii_tokens)
    if not hits:
        return 0.0, []
    return 0.40 + 0.05 * (len(hits) - 1), hits


def recommend(
    source: str | Path,
    intent: str | None = None,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    """Return ranked renderable templates for ``source``.

    Each surviving template is fitted for real; templates whose data contract
    rejects the table are dropped rather than guessed.
    """
    env.ensure_engine_on_path()
    from origin_sciplot.scientific_workflow import (
        prepare_scientific,
        SUPPORTED_SCIENTIFIC_TEMPLATE_IDS,
    )

    source = Path(source)
    candidates: list[dict[str, Any]] = []
    for template_id in sorted(SUPPORTED_SCIENTIFIC_TEMPLATE_IDS):
        manifest = _load_manifest(template_id)
        try:
            prep = prepare_scientific(source, template_id)
        except Exception:  # noqa: BLE001
            continue

        text = _searchable_text(manifest)
        boost, hits = _intent_boost(intent, text, template_id)
        score = float(prep.confidence) + boost
        if prep.requires_confirmation:
            score -= 0.10

        candidates.append(
            {
                "template_id": template_id,
                "name": manifest.get("name", template_id),
                "family": manifest.get("family"),
                "description": manifest.get("description"),
                "plot_kind": prep.plot_spec.plot_kind,
                "score": round(score, 4),
                "mapping_confidence": prep.confidence,
                "requires_confirmation": prep.requires_confirmation,
                "intent_matched_tokens": hits,
                "warnings": list(prep.warnings),
                "ui_order": manifest.get("ui_order", 9999),
            }
        )

    candidates.sort(
        key=lambda item: (-item["score"], item["ui_order"], item["template_id"])
    )
    top = candidates[:limit]
    best = top[0] if top else None
    second_score = top[1]["score"] if len(top) > 1 else None
    margin = (
        round(best["score"] - second_score, 4)
        if best is not None and second_score is not None
        else None
    )
    best_has_intent_hit = bool(best and best["intent_matched_tokens"])
    # No intent keyword matched and the leaders tie: the data alone does not
    # separate the charts, so the AI should confirm instead of silently drawing
    # a catch-all template (e.g. raw_summary) on a meaningless/headless table.
    ambiguous = bool(
        best is not None
        and not best_has_intent_hit
        and (margin is None or margin <= 0.02)
    )
    return {
        "schema_version": "1.0",
        "source": str(source),
        "intent": intent,
        "candidate_count": len(candidates),
        "recommendations": top,
        "auto_selected": best["template_id"] if best else None,
        "auto_selection_score": best["score"] if best else None,
        "auto_selection_margin": margin,
        "auto_selection_ambiguous": ambiguous,
        "gate": {
            "note": "自动选择是建议而非最终决定；豆包会结合你的自然语言目的与你确认后再出图。",
            "needs_user_confirm": bool(
                best and (best["requires_confirmation"] or ambiguous)
            ),
            "reason": (
                "候选图种区分度不足或缺少意图关键词，应先与用户确认"
                if ambiguous
                else ("列映射需确认" if best and best["requires_confirmation"] else None)
            ),
        },
    }
