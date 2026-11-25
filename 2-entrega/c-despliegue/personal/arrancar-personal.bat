@echo off
rem Arranca Raphael PERSONAL en esta PC: harness + orquestador maestro + brigadas instaladas + servidor (API y pagina web).
rem   arrancar-personal.bat                 levanta el servidor en 127.0.0.1:8788 y muestra el chequeo de claves
rem   arrancar-personal.bat chequear        solo dice que falta (modelo local, clave de OpenRouter, brigadas)
rem   arrancar-personal.bat clave           pone o cambia la clave de la app
rem Las claves van en .data\personal\raphael.env (se crea la primera vez; se editan desde la pantalla de Configuracion).
rem Lo instala instalar-personal.bat. Mas en LEEME.md (esta misma carpeta).
setlocal
set "ROOT=%~dp0..\..\.."
pushd "%ROOT%" || exit /b 1
set "ROOT=%CD%"
set "DATOS=%ROOT%\.data\personal"
if not exist "%DATOS%" mkdir "%DATOS%"
if not exist "%DATOS%\installation.yaml" copy /y "%ROOT%\2-entrega\c-despliegue\personal\personal.installation.yaml" "%DATOS%\installation.yaml" >nul
if exist "%ROOT%\.venv\Scripts\python.exe" ( set PY="%ROOT%\.venv\Scripts\python.exe" ) else ( set "PY=py -3.12" )
set PYTHONUTF8=1
rem Desde esta PC se entra sin clave; por Tailscale o desde el celular la clave se sigue pidiendo.
if not defined RAPHAEL_LOCAL_SIN_CLAVE set "RAPHAEL_LOCAL_SIN_CLAVE=1"
set "ACCION=%~1"
if "%ACCION%"=="" (set "ACCION=servir") else shift
%PY% -m raphael_personal_api %ACCION% --instalacion "%DATOS%\installation.yaml" --datos "%DATOS%" %1 %2 %3
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
