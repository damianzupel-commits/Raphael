@echo off
rem Cuentas y APIs: cuentas.bat chequear | probar [--simulado] | plantilla | lienzo   (ver LEEME)
setlocal
set "ROOT=%~dp0..\..\.."
set "PYTHONPATH=%~dp0codigo\src"
if exist "%ROOT%\.venv\Scripts\python.exe" ( "%ROOT%\.venv\Scripts\python.exe" -m raphael_cuentas %* ) else ( py -3.12 -m raphael_cuentas %* )
exit /b %ERRORLEVEL%
