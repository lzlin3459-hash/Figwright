"""Locate the self-contained engine and check the open-source dependencies."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = PRODUCT_ROOT / "engine"
ENGINE_SRC = ENGINE_ROOT / "src"
TEMPLATES_DIR = ENGINE_ROOT / "templates"

# Pure-Python runtime dependencies. Deliberately excludes originpro / OriginExt
# / PySide6 / win32com: Figwright never launches Origin.
REQUIRED_PACKAGES = (
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("matplotlib", "matplotlib"),
    ("openpyxl", "openpyxl"),
    ("xlrd", "xlrd"),
    ("PIL", "pillow"),
    ("yaml", "PyYAML"),
    ("jsonschema", "jsonschema"),
)


def ensure_engine_on_path() -> Path:
    """Insert the bundled engine/src onto sys.path and return it."""
    path = str(ENGINE_SRC)
    if path not in sys.path:
        sys.path.insert(0, path)
    return ENGINE_SRC


def dependency_report() -> list[dict[str, object]]:
    report: list[dict[str, object]] = []
    for import_name, dist_name in REQUIRED_PACKAGES:
        spec = importlib.util.find_spec(import_name)
        version = None
        if spec is not None:
            try:
                module = __import__(import_name)
                version = getattr(module, "__version__", None)
            except Exception:  # noqa: BLE001
                version = None
        report.append(
            {
                "name": dist_name,
                "ok": spec is not None,
                "version": version,
            }
        )
    return report


def engine_ok() -> bool:
    ensure_engine_on_path()
    try:
        from origin_sciplot.scientific_workflow import (  # noqa: F401
            SUPPORTED_SCIENTIFIC_TEMPLATE_IDS,
        )
        from origin_sciplot.scientific_preview import (  # noqa: F401
            _build_scientific_preview_figure,
        )
    except Exception:  # noqa: BLE001
        return False
    return TEMPLATES_DIR.is_dir()
