@echo off
set SCRIPT_DIR=%~dp0

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py "%SCRIPT_DIR%setup.py" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%SCRIPT_DIR%setup.py" %*
  exit /b %ERRORLEVEL%
)

echo Python 3 is required to run this setup script.
exit /b 1
