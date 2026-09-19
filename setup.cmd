@echo off
setlocal enableextensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

REM Locate a 64-bit CPython 3.11/3.12 (the project venv is then built from it).
set "PY="
for %%C in ("py -3.12" "py -3.11" "py -3" "python") do (
  if not defined PY (
    %%~C scripts\check_interp.py >nul 2>nul
    if not errorlevel 1 set "PY=%%~C"
  )
)

if not defined PY (
  echo [Figwright] No 64-bit Python 3.11 or 3.12 was found.
  echo Please install 64-bit Python 3.12 from https://www.python.org/downloads/windows/
  echo tick "Add python.exe to PATH", then run setup.cmd again.
  exit /b 2
)

echo [Figwright] Using base interpreter: %PY%
%PY% scripts\setup.py %*
exit /b %errorlevel%
