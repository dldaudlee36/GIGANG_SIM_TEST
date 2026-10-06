@echo off
setlocal
cd /d "%~dp0"
set "LAUNCH_PY=%~dp0tools\launch.py"
if not exist "%LAUNCH_PY%" (
    if exist "%~dp0app_files\tools\launch.py" set "LAUNCH_PY=%~dp0app_files\tools\launch.py"
)

python -V >nul 2>&1
if not errorlevel 1 (
    python "%LAUNCH_PY%" user %*
    goto finished
)

py -3 -V >nul 2>&1
if not errorlevel 1 (
    py -3 "%LAUNCH_PY%" user %*
    goto finished
)

echo [ERROR] Python 3 executable not found. Please install Python 3 and add to PATH.
pause
exit /b 1

:finished
if errorlevel 1 pause
endlocal
