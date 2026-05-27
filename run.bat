@echo off
setlocal
title Buzzheavier Tool
set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE="
where py >nul 2>nul && set "PYTHON_EXE=py -3"
if not defined PYTHON_EXE where python >nul 2>nul && set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
    echo Python 3 was not found. Install Python or add it to PATH.
    exit /b 1
)
%PYTHON_EXE% "%SCRIPT_DIR%buzzheavier_tool.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Press any key to close...
pause >nul
exit /b %EXIT_CODE%
endlocal
