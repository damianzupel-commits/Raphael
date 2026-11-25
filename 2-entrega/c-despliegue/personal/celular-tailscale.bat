@echo off
rem Publica Raphael personal SOLO dentro de tu red privada de Tailscale (tailnet), para usarlo desde el celular.
rem NO usa Funnel: no queda abierto a internet y no se abre ningun puerto del router.
rem Usa el puerto HTTPS 8443 (no el 443, que en esta PC lo usa el Funnel de Raphael Empresas). Se cambia con RAPHAEL_TS_PORT.
rem Nunca hace "serve reset": no toca lo que ya este publicado (Empresas).
rem Requisitos: Tailscale instalado y con sesion en esta PC y en el celular, y MagicDNS + HTTPS prendidos en la consola de Tailscale.
rem   celular-tailscale.bat           publica 127.0.0.1:8788 por HTTPS dentro de la tailnet
rem   celular-tailscale.bat quitar    deja de publicar SOLO este puerto
if not defined RAPHAEL_TS_PORT set "RAPHAEL_TS_PORT=8443"
if /i "%~1"=="quitar" (
    tailscale serve --https=%RAPHAEL_TS_PORT% off
    exit /b %ERRORLEVEL%
)
tailscale serve --bg --https=%RAPHAEL_TS_PORT% http://127.0.0.1:8788
if errorlevel 1 (
    echo No se pudo publicar. Revisa que Tailscale este prendido y que el puerto %RAPHAEL_TS_PORT% no lo use otra cosa ^(tailscale serve status^).
    exit /b 1
)
echo.
tailscale serve status
echo.
echo Abri esa direccion https://...ts.net:%RAPHAEL_TS_PORT% en el navegador del celular (con Tailscale prendido) y entra con la clave de la app.
echo Pegala tambien en Configuracion ^> "Direccion para el celular".
exit /b 0
