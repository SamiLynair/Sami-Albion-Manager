@echo off
setlocal
cd /d "%~dp0"
title Compilation de Sami Albion Manager

where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 n'est pas installe. Installe Python depuis https://www.python.org/downloads/windows/
  echo Pense a cocher 'Add python.exe to PATH'.
  pause
  exit /b 1
)

if not exist "app.py" (
  echo ERREUR : app.py introuvable !
  echo Tu dois d'abord EXTRAIRE TOUT le ZIP, puis lancer ce script depuis le dossier complet.
  pause
  exit /b 1
)

echo [1/3] Preparation de l'environnement...
py -3 -m venv .venv
if errorlevel 1 goto error

echo [2/3] Installation de Qt et PyInstaller...
".venv\Scripts\python.exe" -m pip install --upgrade pip "PySide6-Essentials>=6.12,<6.13" pyinstaller
if errorlevel 1 goto error

echo [3/3] Creation du programme Windows...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name "Sami Albion Manager" --icon "samialbion.ico" --add-data "samialbion.ico;." --add-data "samialbion\assets\tavern.qss;samialbion\assets" --add-data "samialbion\assets\header_recolte.jpg;samialbion\assets" --add-data "samialbion\assets\ui_click.wav;samialbion\assets" --add-data "samialbion\assets\catalog.json.gz;samialbion\assets" --add-data "samialbion\assets\crafting_recipes.json.gz;samialbion\assets" --add-data "samialbion\assets\market_shop_index.json.gz;samialbion\assets" --add-data "samialbion\assets\item_icons.zip;samialbion\assets" --add-data "samialbion\assets\item_icons_manifest.json;samialbion\assets" --add-data "samialbion\assets\fonts;samialbion\assets\fonts" app.py
if errorlevel 1 goto error

echo.
echo TERMINE ! Le logiciel se trouve dans :
echo %~dp0dist\Sami Albion Manager.exe
echo.
pause
exit /b 0

:error
echo.
echo ERREUR : le programme n'a pas ete compile. Consulte les messages ci-dessus.
pause
exit /b 1
