@echo off
rem Ejecuta las pruebas automatizadas de BibloApp.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual en .venv
    echo Crea el entorno con: python -m venv .venv
    echo Luego instala: .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pytest
pause
