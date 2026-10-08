@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno local...
  py -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo Instalando dependencias...
python -m pip install -r requirements.txt

echo Abriendo Historia Clinica...
start "" http://127.0.0.1:5000
python app.py

pause
