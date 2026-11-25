@echo off
rem Hace que Raphael personal arranque solo cuando inicias sesion en Windows y siga andando con el panel cerrado.
rem Crea la tarea programada "Raphael Personal" (sin ventana, con tu usuario, sin pedir administrador).
rem   instalar-servicio.bat            crea o actualiza la tarea
rem   instalar-servicio.bat quitar     la borra
rem Limite: corre mientras tu sesion de Windows este abierta (bloquear la pantalla o cerrar el panel no la corta).
setlocal
set "TAREA=Raphael Personal"
set "RAPHAEL_VBS=%~dp0arrancar-oculto.vbs"
if /i "%~1"=="quitar" (
    schtasks /End /TN "%TAREA%" >nul 2>&1
    schtasks /Delete /TN "%TAREA%" /F >nul 2>&1
    powershell -NoProfile -Command "Remove-Item -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath('Startup')) 'Raphael Personal.lnk')"
    echo Listo: Raphael ya no arranca solo.
    exit /b 0
)
schtasks /Create /TN "%TAREA%" /TR "wscript.exe \"%RAPHAEL_VBS%\"" /SC ONLOGON /RL LIMITED /F >nul 2>&1
if not errorlevel 1 goto listo
rem Crear una tarea "al iniciar sesion" suele pedir administrador: sin el, va a la carpeta Inicio de tu usuario.
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Startup')) 'Raphael Personal.lnk')); $s.TargetPath='wscript.exe'; $s.Arguments=[char]34+$env:RAPHAEL_VBS+[char]34; $s.Save()"
if errorlevel 1 (
    echo No se pudo dejar Raphael arrancando solo. Podes abrirlo a mano con arrancar-personal.bat
    exit /b 1
)
:listo
echo Listo: Raphael arranca solo al iniciar sesion. Para arrancarlo ahora sin reiniciar:
echo     wscript.exe "%RAPHAEL_VBS%"
echo Si algo falla, el registro esta en .data\personal\servidor.log
exit /b 0
