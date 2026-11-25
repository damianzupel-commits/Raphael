' Lanza arrancar-personal.bat sin ventana y guarda lo que imprime en .data\personal\servidor.log.
' Es lo que ejecuta la tarea programada "Raphael Personal" al iniciar sesion en Windows.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
aca = fso.GetParentFolderName(WScript.ScriptFullName)
raiz = fso.GetAbsolutePathName(aca & "\..\..\..")
datos = raiz & "\.data\personal"
If Not fso.FolderExists(raiz & "\.data") Then fso.CreateFolder(raiz & "\.data")
If Not fso.FolderExists(datos) Then fso.CreateFolder(datos)
sh.Run "cmd /c """"" & aca & "\arrancar-personal.bat"" > """ & datos & "\servidor.log"" 2>&1""", 0, False
