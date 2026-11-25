@echo off
rem Doble clic (acceso directo del escritorio): abre el tunel de Tailscale si hace falta y levanta Raphael Empresas.
rem Cerrar esta ventana apaga el servidor. Las claves van en .data\empresas\raphael.env (ver ..\QUE-CARGAR.md).
chcp 65001 >nul
set PYTHONUTF8=1
title Raphael Empresas
netstat -ano | findstr /c:"127.0.0.1:8787 " | findstr LISTENING >nul
if not errorlevel 1 (
    echo Raphael ya esta prendido en otra ventana. Este es el chequeo:
    echo.
    call "%~dp0arrancar.bat" chequear
    goto fin
)
tailscale funnel status 2>nul | findstr /c:"127.0.0.1:8787" >nul
if errorlevel 1 (
    echo Abriendo el tunel de Tailscale...
    tailscale funnel --bg 8787
    if errorlevel 1 echo AVISO: no se pudo abrir el tunel. Revisa que Tailscale este prendido. Raphael arranca igual, solo en esta PC.
) else (
    echo Tunel de Tailscale: ya estaba abierto.
)
echo.
echo Arrancando Raphael. Deja esta ventana abierta; si la cerras, se apaga.
echo Lo que falte cargar aparece abajo.
echo.
rem Abre la pantalla de Configuracion (claves) en el navegador cuando el servidor ya levanto.
start "" /min cmd /c "timeout /t 6 /nobreak >nul & start http://127.0.0.1:8787/config"
call "%~dp0arrancar.bat"
echo.
echo Raphael se apago.
:fin
echo.
pause
