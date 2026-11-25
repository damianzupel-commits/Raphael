@echo off
rem Publica Raphael personal SOLO dentro de tu red privada de Tailscale (tailnet), para usarlo desde el celular.
rem NO usa Funnel: no queda abierto a internet y no se abre ningun puerto del router.
rem Requisitos: Tailscale instalado y con sesion en esta PC y en el celular, y MagicDNS + HTTPS prendidos en la consola de Tailscale.
rem   celular-tailscale.bat           publica 127.0.0.1:8788 por HTTPS dentro de la tailnet
rem   celular-tailscale.bat quitar    deja de publicarlo
if /i "%~1"=="quitar" (
    tailscale serve reset
    exit /b %ERRORLEVEL%
)
tailscale serve --bg 8788
if errorlevel 1 (
    echo No se pudo publicar. Revisa que Tailscale este prendido y la version: en versiones viejas el comando es "tailscale serve https / http://127.0.0.1:8788".
    exit /b 1
)
echo.
tailscale serve status
echo.
echo Abri esa direccion https://...ts.net en el navegador del celular (con Tailscale prendido) y entra con la clave de la app.
echo Pegala tambien en Configuracion > "Direccion para el celular".
exit /b 0
