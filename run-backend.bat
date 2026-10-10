@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  call install_dependencies.bat
  if errorlevel 1 exit /b 1
)
if not exist ".env" if exist ".env.example" copy ".env.example" ".env" >nul
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
