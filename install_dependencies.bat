@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo Dependencies installed. Run start_backend.bat next.
pause
