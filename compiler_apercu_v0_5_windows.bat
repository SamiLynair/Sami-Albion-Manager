@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Apercu local de la page Recolte - Sami Albion Manager v0.5.1

rem Ceci est un apercu separe : aucune publication GitHub.
rem Le vrai programme deja installe n'est ni modifie ni remplace.

where py >nul 2>nul
if errorlevel 1 (
  echo ERREUR : Python 3 est requis. https://www.python.org/downloads/windows/
  goto failed
)
if not exist "app.py" (
  echo ERREUR : extrais entierement le ZIP de la branche avant de lancer ce fichier.
  goto failed
)

for /f "delims=" %%V in ('py -3 -c "from samialbion import __version__; print(__version__)"') do set "VERSION=%%V"
if not "%VERSION%"=="0.5.1" (
  echo ERREUR : ce script requiert le code de la version 0.5.1 de la branche experimentale.
  echo Version trouvee : %VERSION%
  goto failed
)

echo.
echo === SAMI ALBION MANAGER v%VERSION% - APERCU LOCAL ===
echo [1/4] Preparation de Python...
py -3 -m venv ".venv-apercu"
if errorlevel 1 goto failed
".venv-apercu\Scripts\python.exe" -m pip install --upgrade pip "PySide6-Essentials>=6.12,<6.13" pyinstaller
if errorlevel 1 goto failed

echo [2/4] Verification automatique avant lancement...
set "QT_QPA_PLATFORM=offscreen"
set "SAMI_DISABLE_UPDATE_CHECK=1"
".venv-apercu\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
set "QT_QPA_PLATFORM="

echo [3/4] Creation d'un EXE local distinct...
".venv-apercu\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name "Sami Albion Manager 0.5.1 Apercu" --icon "samialbion.ico" --add-data "samialbion.ico;." --add-data "samialbion\assets\tavern.qss;samialbion\assets" --add-data "samialbion\assets\header_recolte.jpg;samialbion\assets" --add-data "samialbion\assets\catalog.json.gz;samialbion\assets" --add-data "samialbion\assets\crafting_recipes.json.gz;samialbion\assets" --add-data "samialbion\assets\market_shop_index.json.gz;samialbion\assets" --add-data "samialbion\assets\item_icons.zip;samialbion\assets" --add-data "samialbion\assets\item_icons_manifest.json;samialbion\assets" --add-data "samialbion\assets\fonts;samialbion\assets\fonts" app.py
if errorlevel 1 goto failed

echo [4/4] Ouverture de l'apercu...
echo.
echo Fichier : dist\Sami Albion Manager 0.5.1 Apercu.exe
echo La version 0.4.11 deja installee reste intacte.
echo Aucune publication ou mise a jour automatique ne sera effectuee.
echo.
start "" "%~dp0dist\Sami Albion Manager 0.5.1 Apercu.exe"
if errorlevel 1 goto failed
echo.
echo Apercu lance. Ce programme peut etre relance directement depuis dist.
pause
exit /b 0

:failed
echo.
echo ECHEC : l'apercu n'a pas ete lance. Lis l'erreur affichee ci-dessus.
echo Aucune modification de ta version installee ni publication GitHub.
pause
exit /b 1
