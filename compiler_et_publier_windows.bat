@echo off
setlocal
cd /d "%~dp0"
title Compilation et publication - Mon carnet d'artisan

where py >nul 2>nul
if errorlevel 1 (
  echo ERREUR : Python 3 est requis. https://www.python.org/downloads/windows/
  goto failed
)
where gh >nul 2>nul
if errorlevel 1 (
  echo ERREUR : GitHub CLI est requis. https://cli.github.com/
  echo Apres installation, ouvre un nouveau terminal et lance : gh auth login
  goto failed
)
if not exist "app.py" (
  echo ERREUR : extrais entierement le ZIP du depot avant de lancer ce fichier.
  goto failed
)
gh auth status >nul 2>nul
if errorlevel 1 (
  echo.
  echo Connexion GitHub necessaire, uniquement au premier lancement...
  gh auth login
  if errorlevel 1 goto failed
)
for /f "delims=" %%V in ('py -3 -c "from samialbion import __version__; print(__version__)"') do set "VERSION=%%V"
if not defined VERSION (
  echo ERREUR : version introuvable.
  goto failed
)
echo.
echo Version a publier : v%VERSION%
gh release view "v%VERSION%" --repo SamiLynair/Sami-Albion-Manager >nul 2>nul
if not errorlevel 1 (
  echo ERREUR : la release v%VERSION% existe deja. Incremente la version avant une nouvelle publication.
  goto failed
)
echo [1/4] Preparation Python...
py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --upgrade pip "PySide6-Essentials>=6.12,<6.13" pyinstaller
if errorlevel 1 goto failed
echo [2/4] Tests...
set "QT_QPA_PLATFORM=offscreen"
set "SAMI_DISABLE_UPDATE_CHECK=1"
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
echo [3/4] Compilation Windows...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name "Sami Albion Manager" --icon "samialbion.ico" --add-data "samialbion.ico;." --add-data "samialbion\assets\tavern.qss;samialbion\assets" --add-data "samialbion\assets\header_recolte.jpg;samialbion\assets" --add-data "samialbion\assets\catalog.json.gz;samialbion\assets" --add-data "samialbion\assets\crafting_recipes.json.gz;samialbion\assets" --add-data "samialbion\assets\market_shop_index.json.gz;samialbion\assets" --add-data "samialbion\assets\item_icons.zip;samialbion\assets" --add-data "samialbion\assets\item_icons_manifest.json;samialbion\assets" --add-data "samialbion\assets\fonts;samialbion\assets\fonts" app.py
if errorlevel 1 goto failed
copy /Y "dist\Sami Albion Manager.exe" "dist\Sami-Albion-Manager-Windows.exe" >nul
if errorlevel 1 goto failed
echo [4/4] Publication GitHub Releases...
gh release create "v%VERSION%" "dist\Sami-Albion-Manager-Windows.exe" --repo SamiLynair/Sami-Albion-Manager --title "v%VERSION%" --generate-notes --target main
if errorlevel 1 goto failed
echo.
echo SUCCES : v%VERSION% publiee. Les utilisateurs peuvent la recevoir via Mises a jour.
pause
exit /b 0

:failed
echo.
echo ECHEC : aucune publication effectuee par ce script. Lis l'erreur ci-dessus.
pause
exit /b 1
