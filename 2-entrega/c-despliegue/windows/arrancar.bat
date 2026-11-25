@echo off
rem Arranca Raphael Empresas en la PC de Windows: harness + orquestador (Secretaria) + brigada Empresas + API + canal de Meta.
rem   arrancar.bat                 levanta el servidor en 127.0.0.1:8787 (lo expone el tunel) y muestra el chequeo de claves
rem   arrancar.bat chequear        solo dice que claves faltan (con --real exige tambien IA, Meta real y perfil de la clienta)
rem   arrancar.bat clave           pone o cambia la clave de la duena para la app
rem Las claves se cargan en .data\empresas\raphael.env (se crea la primera vez). Mas en 2-entrega\c-despliegue\QUE-CARGAR.md
setlocal
set "ROOT=%~dp0..\..\.."
pushd "%ROOT%" || exit /b 1
set "ROOT=%CD%"
set "DATOS=%ROOT%\.data\empresas"
if not exist "%DATOS%" mkdir "%DATOS%"
if not exist "%DATOS%\installation.yaml" copy /y "%ROOT%\2-entrega\c-despliegue\instalacion-clienta\clienta.installation.yaml" "%DATOS%\installation.yaml" >nul
if not exist "%DATOS%\raphael.env" (
    copy /y "%ROOT%\2-entrega\c-despliegue\raphael.env.plantilla" "%DATOS%\raphael.env" >nul
    echo Se creo %DATOS%\raphael.env : completalo con tus claves y volve a correr esto.
)
if exist "%ROOT%\.venv\Scripts\python.exe" ( set "PY=%ROOT%\.venv\Scripts\python.exe" ) else ( set "PY=py -3.12" )
set "PYTHONPATH=%ROOT%\1-harness\b-codigo\src;%ROOT%\1-harness\c-brigadas\00-orquestador\b-codigo\src;%ROOT%\1-harness\c-brigadas\15-empresas\b-codigo\src;%ROOT%\2-entrega\b-codigo\servidor\api\src"
set "ACCION=%~1"
if "%ACCION%"=="" (set "ACCION=servir") else shift
%PY% -m raphael_empresas_api %ACCION% --instalacion "%DATOS%\installation.yaml" --datos "%DATOS%" %1 %2 %3
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
