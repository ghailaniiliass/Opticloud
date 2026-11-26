@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo   Opti Cloud : installation et premier lancement
echo ============================================================
echo.
echo Avant de continuer : WAMP doit etre demarre (icone VERTE).
echo.
where python >nul 2>nul
if errorlevel 1 (
    echo ERREUR : Python est introuvable.
    echo Installez Python 3.12 ou plus recent depuis python.org et cochez "Add python.exe to PATH".
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python...
    python -m venv .venv
    if errorlevel 1 (
        echo ERREUR : creation de l'environnement impossible.
        pause
        exit /b 1
    )
)
call ".venv\Scripts\activate.bat"
echo Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR : installation des dependances impossible.
    pause
    exit /b 1
)
echo.
python setup_local.py
if errorlevel 1 (
    echo.
    echo L'installation s'est arretee : lisez le message ci-dessus.
    pause
    exit /b 1
)
echo.
echo Demarrage du serveur. Ouvrez http://127.0.0.1:8000/ dans votre navigateur.
echo Pour arreter le serveur : fermez cette fenetre ou appuyez sur Ctrl+C.
start "" "http://127.0.0.1:8000/"
python manage.py runserver
pause
