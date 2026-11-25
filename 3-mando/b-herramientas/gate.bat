@echo off
rem Puerta del monorepo: corre todas las suites y ruff. Sale con 0 si todo pasa, 2 si algo falla.
setlocal
set "ROOT=%~dp0..\.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
    "%ROOT%\.venv\Scripts\python.exe" "%~dp0gate.py" %*
) else (
    py -3.12 "%~dp0gate.py" %*
)
exit /b %ERRORLEVEL%
