@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
if not exist ".env" copy .env.example .env >nul
uvicorn app.main:app --reload --port 8000
