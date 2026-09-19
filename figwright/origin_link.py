"""Bridge to the OPTIONAL Origin backup backend.

This module is deliberately **stdlib-only**. It never imports originpro / OriginExt
itself; those live in a separate product-managed environment (``.venv-origin``) with a
different numpy/pandas stack. We only launch that environment's interpreter as a child
process and parse its JSON-lines worker protocol.

The default matplotlib backend does not touch any of this.

Licensing gate
--------------
The smoke test reports ``passed`` only when Origin can actually save a non-empty
editable ``.opju``. A Learning/Trial installation reports ``degraded`` (project save
restricted). In the degraded state we refuse to deliver a formal ``.opju`` and never
attempt to remove the Origin demo watermark.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
ORIGIN_RUNTIME = PRODUCT_ROOT / "origin_runtime"
ORIGIN_SRC = ORIGIN_RUNTIME / "src"
ORIGIN_TEMPLATES = ORIGIN_RUNTIME / "templates"
ORIGIN_REQUIREMENTS = ORIGIN_RUNTIME / "requirements-origin.txt"
ORIGIN_VENV = PRODUCT_ROOT / ".venv-origin"
ORIGIN_PY = ORIGIN_VENV / "Scripts" / "python.exe"
SMOKE_CACHE = PRODUCT_ROOT / ".origin-smoke.json"
DEFAULT_SMOKE_DIR = PRODUCT_ROOT / ".origin-smoke-out"

SMOKE_MODULE = "origin_sciplot.workers.origin_smoke_worker"
RENDER_MODULE = "origin_sciplot.workers.run_template_worker"
SMOKE_REPORT_NAME = "compatibility-report.json"

# Public, stable exit codes used by the CLI.
RC_OK = 0
RC_USAGE = 2
RC_NEEDS_CONFIRMATION = 3
RC_ORIGIN_TECHNICAL = 4
RC_LICENSE_CONFIRMATION = 5
RC_ORIGIN_LIMITED = 6


class OriginBackendError(RuntimeError):
    """A failure in the optional Origin backend with a stable code."""

    def __init__(self, code: str, message: str, *, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.message = message


def runtime_files_present() -> bool:
    """Whether the vendored Origin runtime ships in this product folder."""

    return (
        (ORIGIN_SRC / "origin_sciplot").is_dir()
        and ORIGIN_TEMPLATES.is_dir()
        and ORIGIN_REQUIREMENTS.is_file()
    )


def origin_venv_installed() -> bool:
    return ORIGIN_PY.is_file()


def _worker_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ORIGIN_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def origin_env_report() -> dict[str, Any]:
    """Read-only report about the optional Origin environment (never launches Origin)."""

    report: dict[str, Any] = {
        "shipped": runtime_files_present(),
        "venv_dir": str(ORIGIN_VENV),
        "installed": origin_venv_installed(),
        "ready": False,
    }
    if not runtime_files_present():
        report["note"] = "vendored Origin runtime not found"
        return report
    if not origin_venv_installed():
        report["note"] = "install with: setup.cmd --with-origin"
        return report

    # Importing originpro does NOT activate Origin; activation starts at set_show().
    probe = (
        "import json, importlib.metadata as md\n"
        "v={}\n"
        "for d in ('originpro','OriginExt','numpy','pandas','matplotlib'):\n"
        "    try: v[d]=md.version(d)\n"
        "    except Exception: v[d]=None\n"
        "ok=False\n"
        "try:\n"
        "    import originpro  # noqa: F401\n"
        "    ok=bool(getattr(originpro,'oext',False))\n"
        "except Exception as e:\n"
        "    v['import_error']=type(e).__name__+': '+str(e)[:200]\n"
        "v['originpro_external_automation']=ok\n"
        "print('FIGWRIGHT_PROBE'+json.dumps(v)+'PROBE_END')\n"
    )
    try:
        proc = subprocess.run(
            [str(ORIGIN_PY), "-c", probe],
            cwd=str(ORIGIN_RUNTIME),
            env=_worker_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report
    if proc.returncode != 0:
        report["error"] = (proc.stderr or proc.stdout or "import probe failed")[-400:]
        return report
    payload = _extract_probe_json(proc.stdout)
    if payload is None:
        report["error"] = "could not parse Origin environment probe"
        return report
    report["packages"] = {
        k: payload.get(k) for k in ("originpro", "OriginExt", "numpy", "pandas", "matplotlib")
    }
    report["external_automation_available"] = bool(
        payload.get("originpro_external_automation")
    )
    if payload.get("import_error"):
        report["error"] = payload["import_error"]
    report["ready"] = bool(
        payload.get("originpro_external_automation")
        and payload.get("originpro")
        and payload.get("numpy")
    )
    return report


def _extract_probe_json(stdout: str) -> dict[str, Any] | None:
    marker_a, marker_b = "FIGWRIGHT_PROBE", "PROBE_END"
    start = stdout.find(marker_a)
    end = stdout.find(marker_b, start + len(marker_a) if start >= 0 else 0)
    if start < 0 or end < 0:
        return None
    raw = stdout[start + len(marker_a) : end].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def detect_com_registration() -> dict[str, bool]:
    """Read-only registry check for Origin Automation ProgIDs (does not launch Origin)."""

    result = {"Origin.Application": False, "Origin.ApplicationSI": False}
    if os.name != "nt":
        return result
    try:
        import winreg  # type: ignore
    except Exception:  # noqa: BLE001
        return result
    for progid in result:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid) as handle:
                winreg.QueryValueEx(handle, "")  # raises if malformed
            result[progid] = True
        except OSError:
            result[progid] = False
    return result


def _run_worker(
    worker_args: list[str],
    *,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run an Origin worker to completion in the separate venv (no hard kill)."""

    if not origin_venv_installed():
        raise OriginBackendError(
            "origin_backend_not_installed",
            "可选 Origin 后端尚未安装，请先运行: setup.cmd --with-origin",
        )
    cmd = [str(ORIGIN_PY), *worker_args]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ORIGIN_RUNTIME),
        env=_worker_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    events: list[dict[str, Any]] = []
    terminal: dict[str, Any] | None = None
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        kind = event.get("type")
        if kind in ("done", "error"):
            terminal = event
        if on_event is not None:
            try:
                on_event(event)
            except Exception:  # noqa: BLE001 - reporting must not break the run
                pass
    returncode = proc.wait()
    return {"returncode": returncode, "events": events, "terminal": terminal}


def read_smoke_report(output_dir: str | Path) -> dict[str, Any] | None:
    path = Path(output_dir) / SMOKE_REPORT_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def save_smoke_cache(report: dict[str, Any]) -> None:
    cache = {
        "checked_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "status": report.get("status"),
        "report": report,
    }
    SMOKE_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_smoke_cache() -> dict[str, Any] | None:
    if not SMOKE_CACHE.is_file():
        return None
    try:
        return json.loads(SMOKE_CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def run_smoke(
    output_dir: str | Path | None = None,
    *,
    keep_open: bool = False,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the live Origin smoke test. Status: passed | degraded | failed."""

    target = Path(output_dir) if output_dir else DEFAULT_SMOKE_DIR
    target.mkdir(parents=True, exist_ok=True)
    args = [
        "-m",
        SMOKE_MODULE,
        "--output-dir",
        str(target),
        "--keep-origin-open" if keep_open else "--close-origin",
    ]
    run = _run_worker(args, on_event=on_event)
    terminal = run["terminal"] or {}
    if run["returncode"] != 0 or terminal.get("type") == "error":
        raise OriginBackendError(
            terminal.get("code", "origin_smoke_failed"),
            terminal.get("message", "Origin 连通性自检未通过。"),
            stage=terminal.get("stage"),
        )
    report = read_smoke_report(target) or {}
    status = report.get("status") or terminal.get("status") or "failed"
    if status not in ("passed", "degraded"):
        raise OriginBackendError("origin_smoke_inconclusive", f"smoke 状态异常: {status}")
    report.setdefault("status", status)
    report["output_dir"] = str(target)
    save_smoke_cache(report)
    return report


def passed_smoke_cached() -> dict[str, Any] | None:
    cache = load_smoke_cache()
    if cache and cache.get("status") == "passed":
        return cache
    return None


def run_render(
    source: str | Path,
    template_id: str,
    output_dir: str | Path,
    *,
    keep_open: bool = False,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Render via the isolated Origin worker. Caller must have gated on smoke=passed."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    args = [
        "-m",
        RENDER_MODULE,
        "--template-id",
        template_id,
        "--input-csv",
        str(source),
        "--output-dir",
        str(target),
        "--keep-origin-open" if keep_open else "--close-origin",
    ]
    run = _run_worker(args, on_event=on_event)
    terminal = run["terminal"] or {}
    if run["returncode"] != 0 or terminal.get("type") == "error":
        raise OriginBackendError(
            terminal.get("code", "origin_render_failed"),
            terminal.get("message", "Origin 渲染失败。"),
            stage=terminal.get("stage"),
        )
    return terminal


def collect_origin_artifacts(output_dir: str | Path) -> dict[str, Any]:
    """Inspect the output folder for non-empty Origin deliverables."""

    target = Path(output_dir)
    files: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for ext in ("opju", "png", "pdf", "tif"):
        candidate = target / f"result.{ext}"
        if candidate.is_file() and candidate.stat().st_size > 0:
            files[ext] = str(candidate)
            sizes[ext] = candidate.stat().st_size
    verify_report = target / "origin_verify_report.json"
    return {
        "files": files,
        "bytes": sizes,
        "verify_report": str(verify_report) if verify_report.is_file() else None,
        "has_opju": "opju" in files,
    }
