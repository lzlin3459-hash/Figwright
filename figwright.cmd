@echo off
setlocal enableextensions
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [Figwright] Not installed yet. Please run setup.cmd in this folder first.
  exit /b 2
)

"%PY%" -m figwright %*
exit /b %errorlevel%
