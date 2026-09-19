# Vendored Origin runtime (OPTIONAL backend — experimental)

This directory is a **verbatim, vendored copy** of the analytical/Origin runtime from the
upstream project **EditaPlot** (`hang-jin/editaplot`, Apache License 2.0). It is distributed
inside Figwright solely to power the **optional** Origin backup backend.

## What this is

- `origin_sciplot/` — full upstream Python package, including `origin_backend/` (COM automation,
  renderers, smoke test, verification) and `workers/` (subprocess entry points).
- `templates/` — upstream template specs, each with its thin Origin `runner.py` / `service.py`.
- `requirements-origin.txt` — the dependency stack pinned for the Origin backend
  (`originpro`, `OriginExt`, numpy 1.26 / pandas 2.3 / matplotlib 3.10, ...).

## How it is isolated

- The **main** Figwright backend (pure matplotlib) never imports this directory and never needs
  these packages. The main `.venv` stays on numpy 2.x / pandas 3.x.
- This runtime is executed only by a **separate** product-managed virtual environment
  (`.venv-origin`), created on demand via `setup.cmd --with-origin`, and only in child processes:
  - smoke: `python -m origin_sciplot.workers.origin_smoke_worker --output-dir <dir>`
  - render: `python -m origin_sciplot.workers.run_template_worker --template-id <id> --input-csv <file> ...`

## Licensing and the watermark boundary

- This is **source code only**. It does **not** contain, install, crack, or bypass Origin/OriginPro.
- You must supply your own **properly licensed, activated Origin/OriginPro 2021+** on Windows.
- The smoke test reports `passed` only when a non-empty editable `.opju` can actually be saved.
  A Learning/Trial environment reports `degraded` (project save restricted; image export works):
  in that state Figwright does **not** deliver a formal `.opju` and never removes the Origin
  demo watermark. Use the default matplotlib backend for watermark-free figures.
- Attribution and the modification notice are in the root `NOTICE` file.
