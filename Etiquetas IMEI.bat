@echo off
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version >nul 2>nul || (
  echo.
  echo Python nao encontrado. Instale em https://www.python.org/downloads/
  echo e marque a opcao "Add python.exe to PATH" na instalacao.
  pause
  exit /b 1
)
echo Abrindo Etiquetas IMEI...
start "" http://localhost:8100
%PY% -m etiquetas_imei
pause
