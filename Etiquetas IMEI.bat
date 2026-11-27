@echo off
cd /d "%~dp0"
echo Abrindo Etiquetas IMEI...
start "" http://localhost:8100
python -m etiquetas_imei
pause
