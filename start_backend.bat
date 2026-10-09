@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run install_dependencies.bat first.& pause & exit /b 1)
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
pause
