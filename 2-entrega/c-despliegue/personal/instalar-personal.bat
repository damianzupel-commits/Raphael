@echo off
rem Instalador de Raphael personal para Windows. Doble clic y listo; se puede repetir sin problema (actualiza).
rem Hace: entorno Python (.venv), instala el harness, el orquestador, el servidor y las brigadas del repo, prepara
rem .data\personal, deja el servidor arrancando solo con Windows, crea el acceso directo y corre el chequeo.
rem Necesita Python 3.12 (py launcher). No instala nada fuera de .venv. No pide administrador.
setlocal
set "ROOT=%~dp0..\..\.."
pushd "%ROOT%" || exit /b 1
set "ROOT=%CD%"
set PYTHONUTF8=1
echo === Raphael personal: instalacion ===
if not exist "%ROOT%\.venv\Scripts\python.exe" (
    echo Creando el entorno Python en %ROOT%\.venv ...
    py -3.12 -m venv "%ROOT%\.venv" || ( echo No encuentro Python 3.12. Instalalo desde python.org y reintenta. & goto falla )
)
set "PY=%ROOT%\.venv\Scripts\python.exe"
"%PY%" -m pip install -q --upgrade pip
echo Instalando el nucleo, el orquestador y el servidor...
"%PY%" -m pip install -q -e "%ROOT%\1-harness\b-codigo" -e "%ROOT%\1-harness\c-brigadas\00-orquestador\b-codigo" -e "%ROOT%\2-entrega\b-codigo\servidor\api" || goto falla
echo Instalando las brigadas que haya en el repo...
for /d %%D in ("%ROOT%\1-harness\c-brigadas\*") do (
    if /i not "%%~nxD"=="00-orquestador" if exist "%%D\b-codigo\pyproject.toml" (
        echo   %%~nxD
        "%PY%" -m pip install -q -e "%%D\b-codigo" || echo   AVISO: %%~nxD no se pudo instalar; el servidor la marca y sigue con las demas.
    )
)
call "%~dp0arrancar-personal.bat" chequear
echo.
echo Dejando Raphael como servicio de fondo (arranca con Windows)...
call "%~dp0instalar-servicio.bat"
schtasks /Run /TN "Raphael Personal" >nul 2>&1
echo Creando el acceso directo "Raphael" en el escritorio...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Raphael.url'); $s.TargetPath='http://127.0.0.1:8788/'; $s.Save()" 
echo.
echo Listo. Abri http://127.0.0.1:8788/ . La primera vez la clave de la app esta en .data\personal\clave-inicial.txt
echo Para el celular: celular-tailscale.bat. Para las claves: pestana Configuracion. Mas en LEEME.md
popd
exit /b 0
:falla
echo.
echo La instalacion se corto. Mira el mensaje de arriba, arregla eso y volve a correr este archivo.
popd
exit /b 1
