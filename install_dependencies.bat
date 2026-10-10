@echo off
setlocal
cd /d "%~dp0"
echo.
echo SkillSync backend dependency installer
echo For Windows path-length problems, extract the project to C:\SkillSync first.
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher not found. Install Python 3.11 or newer and enable Add Python to PATH.
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo Could not create virtual environment. Confirm Python 3.11 is installed.
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Dependencies installed successfully.
echo Next, run start_backend.bat
exit /b 0
:failed
echo.
echo Installation failed. If the error mentions Windows path length, move the project to C:\SkillSync and run this installer again.
exit /b 1
