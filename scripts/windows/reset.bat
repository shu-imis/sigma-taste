@echo off
setlocal

cd /d "%~dp0\..\.."
if errorlevel 1 goto :error

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY_CMD=py"
) else (
  set "PY_CMD=python"
)

if exist "db.sqlite3" del "db.sqlite3"

if not exist ".venv\Scripts\python.exe" (
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :error
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto :error

python -m pip install -r requirements.txt
if errorlevel 1 goto :error

python manage.py migrate
if errorlevel 1 goto :error

echo Database reset complete.
exit /b 0

:error
echo Windows reset failed.
exit /b 1
