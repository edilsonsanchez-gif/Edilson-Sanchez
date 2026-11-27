@echo off
rem Arraste o .txt das etiquetas sobre este atalho, ou de dois cliques para imprimir o mais recente da pasta Downloads.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0imprimir_txt.ps1" -Arquivo "%~1"
if errorlevel 1 (pause) else (timeout /t 3 >nul)
