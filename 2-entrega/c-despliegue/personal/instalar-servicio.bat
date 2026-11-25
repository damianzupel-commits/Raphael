@echo off
rem Hace que Raphael personal arranque solo cuando inicias sesion en Windows y siga andando con el panel cerrado.
rem Crea la tarea programada "Raphael Personal" (sin ventana, con tu usuario, sin pedir administrador).
rem   instalar-servicio.bat            crea o actualiza la tarea
rem   instalar-servicio.bat quitar     la borra
rem Limite: corre mientras tu sesion de Windows este abierta (bloquear la pantalla o cerrar el panel no la corta).
setlocal
set "TAREA=Raphael Personal"
if /i "%~1"=="quitar" (
    schtasks /End /TN "%TAREA%" >nul 2>&1
    schtasks /Delete /TN "%TAREA%" /F
    exit /b %ERRORLEVEL%
)
schtasks /Create /TN "%TAREA%" /TR "wscript.exe \"%~dp0arrancar-oculto.vbs\"" /SC ONLOGON /RL LIMITED /F
if errorlevel 1 (
    echo No se pudo crear la tarea. Proba abrir esta ventana como tu usuario normal y reintentar.
    exit /b 1
)
echo Listo: Raphael arranca solo al iniciar sesion. Para arrancarlo ahora sin reiniciar:
echo     schtasks /Run /TN "%TAREA%"
echo Si algo falla, el registro esta en .data\personal\servidor.log
exit /b 0
