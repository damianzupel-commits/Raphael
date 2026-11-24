@echo off
REM ============================================================
REM  Raphael - Panel del harness v2 (pieza 01-harness)
REM  La primera vez arma su entorno en ..\.venv; despues abre directo.
REM ============================================================
setlocal
title Raphael - Panel del harness v2
cd /d "%~dp0.."
set "VENV=%CD%\.venv"
REM .listo-v2: si cambian las dependencias se sube el numero y se reinstala solo
if exist "%VENV%\.listo-v2" if exist "%VENV%\Scripts\pythonw.exe" goto abrir

echo Preparando el panel del harness (solo la primera vez)...
set "PY="
for %%V in (3.13 3.12 3.11) do (
  if not defined PY (
    py -%%V -c "import tkinter" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo.
  echo No encontre Python 3.11 o mas nuevo con tkinter.
  echo Instalalo desde python.org ^(con la opcion "tcl/tk and IDLE"^) y volve a abrir esto.
  pause
  exit /b 1
)
echo Usando: %PY%
if exist "%VENV%\Scripts\python.exe" goto instalar
%PY% -m venv "%VENV%" || goto fallo
:instalar
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r "%CD%\panel\requirements.txt" || goto fallo
echo listo> "%VENV%\.listo-v2"

:abrir
start "" "%VENV%\Scripts\pythonw.exe" "%CD%\panel\harness_panel.py"
exit /b 0

:fallo
echo.
echo Algo fallo armando el entorno. Revisa el mensaje de arriba.
pause
exit /b 1
