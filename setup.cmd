@echo off
setlocal enableextensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

REM Detect a double-click from Explorer (its command line carries the full
REM quoted path to this file). A normal "setup.cmd" typed in a console does
REM NOT match, so automation / Skill installs are never blocked by pause.
set "DOUBLECLICK=0"
echo %cmdcmdline% | find /i "%~f0" >nul && set "DOUBLECLICK=1"

REM Refuse to run when the package was not fully extracted (e.g. opened inside
REM the ZIP or an archive's temp folder).
if not exist "scripts\setup.py" (
  echo.
  echo [Figwright] ERROR: Required files are missing ^(scripts\setup.py^).
  echo.
  echo You probably ran setup.cmd from INSIDE the downloaded ZIP.
  echo   1^) Right-click Figwright-v0.1.0.zip  ^>  "Extract All..."
  echo   2^) Open the EXTRACTED Figwright folder
  echo   3^) Run setup.cmd there
  echo.
  if "%DOUBLECLICK%"=="1" pause
  exit /b 2
)

REM Locate a 64-bit CPython 3.11/3.12 (the project venv is then built from it).
set "PY="
for %%C in ("py -3.12" "py -3.11" "py -3" "python") do (
  if not defined PY (
    %%~C scripts\check_interp.py >nul 2>nul
    if not errorlevel 1 set "PY=%%~C"
  )
)

if not defined PY (
  echo.
  echo [Figwright] ERROR: No suitable 64-bit Python 3.11 or 3.12 was found.
  echo.
  echo How to fix:
  echo   1. Download 64-bit Python 3.12 from https://www.python.org/downloads/windows/
  echo   2. On the FIRST installer screen, TICK "Add python.exe to PATH".
  echo   3. Click "Install Now", then close THIS window and run setup.cmd again.
  echo.
  echo ^(No log is written at this stage because Python itself is missing.^)
  if "%DOUBLECLICK%"=="1" pause
  exit /b 2
)

echo [Figwright] Using base interpreter: %PY%
%PY% scripts\setup.py %*
set "RC=%errorlevel%"

if not "%RC%"=="0" (
  echo.
  echo [Figwright] Setup FAILED ^(exit code %RC%^).
  echo If this keeps happening, send the file "setup-log.txt" in this folder
  echo to the maintainer. You can also open cmd here and run:  setup.cmd
  echo.
  if "%DOUBLECLICK%"=="1" pause
  exit /b %RC%
)

if "%DOUBLECLICK%"=="1" (
  echo.
  echo === Setup finished. You can close this window now. ===
  pause
)
exit /b 0
