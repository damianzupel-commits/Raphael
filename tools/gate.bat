@echo off
rem Puerta del monorepo: corre las cuatro suites y ruff. Sale con 0 si todo pasa, 2 si algo falla.
setlocal
set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
    "%ROOT%\.venv\Scripts\python.exe" "%ROOT%\tools\gate.py" %*
) else (
    py -3.12 "%ROOT%\tools\gate.py" %*
)
exit /b %ERRORLEVEL%
