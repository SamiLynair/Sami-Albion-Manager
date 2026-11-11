@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 est requis. https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
py -3 -c "import PySide6" >nul 2>nul
if errorlevel 1 (
  echo Installation du composant graphique Qt...
  py -3 -m pip install "PySide6-Essentials>=6.12,<6.13"
  if errorlevel 1 goto error
)
py -3 app.py
if errorlevel 1 pause
exit /b 0

:error
echo Installation impossible. Reessaie plus tard ou utilise build_windows.bat.
pause
exit /b 1
