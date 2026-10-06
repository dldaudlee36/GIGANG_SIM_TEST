@echo off
setlocal
cd /d "%~dp0"
set "STOP_PY=%~dp0tools\stop.py"
if not exist "%STOP_PY%" (
    if exist "%~dp0app_files\tools\stop.py" set "STOP_PY=%~dp0app_files\tools\stop.py"
)

python -V >nul 2>&1
if not errorlevel 1 (
    python "%STOP_PY%" admin %*
    goto finished
)

py -3 -V >nul 2>&1
if not errorlevel 1 (
    py -3 "%STOP_PY%" admin %*
    goto finished
)

echo [ERROR] Python 3 executable not found. Please install Python 3 and add to PATH.
pause
exit /b 1

:finished
if errorlevel 1 pause
endlocal
