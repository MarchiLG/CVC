@echo off
REM run.bat -- sets up the environment (the first time) and runs the
REM application (Computer Vision Central, web interface: HTML/CSS/JS in
REM the browser) on Windows.
REM
REM It is the Windows equivalent of ./run-html.sh -- same backend
REM (cameras, YOLO, alerts, narrator), same web UI, just launched
REM without bash. Double-clicking this file from Explorer works too.
REM
REM Usage:
REM   run.bat                  starts and opens the browser at localhost:8000
REM   run.bat --port 9000      listens on another port
REM   run.bat --host 0.0.0.0   exposes it on the local network (NO auth!)
REM   run.bat --no-browser     does not open the browser automatically
REM   run.bat --reinstall      forces reinstalling dependencies
REM
REM Any other argument is passed straight through to src\main_web.py.

setlocal enabledelayedexpansion

cd /d "%~dp0"

set "VENV_DIR=.venv"
set "REINSTALL=0"

REM --reinstall is consumed here; everything else goes to Python.
set "ARGS="
for %%A in (%*) do (
    if /I "%%~A"=="--reinstall" (
        set "REINSTALL=1"
    ) else (
        set "ARGS=!ARGS! "%%~A""
    )
)

REM Prefer the Python launcher (py -3) when available, since it is what
REM the official python.org installer registers on Windows; fall back
REM to "python" for other installs (Microsoft Store, conda, ...).
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PY_LAUNCHER=py -3"
) else (
    set "PY_LAUNCHER=python"
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ==^> No virtual environment found at %VENV_DIR% -- creating it...
    %PY_LAUNCHER% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create the virtual environment. Is Python 3 installed and on PATH?
        exit /b 1
    )
    set "REINSTALL=1"
)

set "PYTHON=%VENV_DIR%\Scripts\python.exe"

REM The web UI needs fastapi/uvicorn, which may be missing from a venv
REM created before this interface existed -- install them on demand.
if "%REINSTALL%"=="0" (
    "%PYTHON%" -c "import fastapi, uvicorn" >nul 2>nul
    if errorlevel 1 (
        echo ==^> Web interface dependencies missing -- installing them.
        set "REINSTALL=1"
    )
)

if "%REINSTALL%"=="1" (
    echo ==^> Installing dependencies ^(this can take a while the first time --
    echo     torch, ultralytics and insightface together are over 1GB of download^).
    "%PYTHON%" -m pip install --upgrade pip -q
    "%PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed -- see the pip output above.
        exit /b 1
    )
)

if not exist ".env" (
    echo ==^> .env not found -- copying .env.example.
    echo     Edit .env with your real camera credentials before continuing.
    copy /Y ".env.example" ".env" >nul
)

echo ==^> Starting Computer Vision Central ^(web interface^)...
"%PYTHON%" src\main_web.py !ARGS!
