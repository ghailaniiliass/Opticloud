@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo L'installation n'a pas encore ete faite : lancez d'abord INSTALLER_ET_LANCER.bat
    pause
    exit /b 1
)
if not exist ".env" (
    echo Le fichier .env est introuvable : lancez d'abord INSTALLER_ET_LANCER.bat
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
echo Opti Cloud : demarrage. WAMP doit etre demarre (icone VERTE).
echo Ouvrez http://127.0.0.1:8000/ dans votre navigateur.
start "" "http://127.0.0.1:8000/"
python manage.py runserver
pause
