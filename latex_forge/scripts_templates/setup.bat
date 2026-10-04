@echo off
rem Set this LaTeX project up on the current machine (see setup.py --help).
set SCRIPT_DIR=%~dp0

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%SCRIPT_DIR%setup.py" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>nul
  if not errorlevel 1 (
    python "%SCRIPT_DIR%setup.py" %*
    exit /b %ERRORLEVEL%
  )
)

rem No usable Python: uv can run the script with a Python it downloads itself.
where uv >nul 2>nul
if %ERRORLEVEL%==0 (
  uv run --no-project --python 3.12 "%SCRIPT_DIR%setup.py" %*
  exit /b %ERRORLEVEL%
)
if exist "%USERPROFILE%\.local\bin\uv.exe" (
  "%USERPROFILE%\.local\bin\uv.exe" run --no-project --python 3.12 "%SCRIPT_DIR%setup.py" %*
  exit /b %ERRORLEVEL%
)

echo Python 3.8+ is required to run this setup script.
echo Install it, or install uv (which brings its own Python) and run this script again:
echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
exit /b 1
