@echo off
setlocal
cd /d "%~dp0.."
set "BIBLOAPP_DB=%~dp0vencidos_demo.db"

if not exist "%BIBLOAPP_DB%" (
    echo Creando la base de demostracion...
    ".venv\Scripts\python.exe" "%~dp0crear_demo_vencidos.py"
    if errorlevel 1 pause
)

echo Abriendo BibloApp con la base de demostracion:
echo %BIBLOAPP_DB%
echo.
".venv\Scripts\python.exe" -m app.main
if errorlevel 1 pause
