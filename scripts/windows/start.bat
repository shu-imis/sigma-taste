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

python manage.py runserver
exit /b %errorlevel%

:error
echo Windows startup failed.
exit /b 1
