# 2-entrega/b-codigo/panel-escritorio

Panel nativo de Raphael personal (tkinter + Pillow) con la estética del orquestador: arriba las brigadas montadas y "Agregar brigadas", a la izquierda el chat (uno por brigada y uno del orquestador), a la derecha cocineros, efímeros y herramientas, y la esfera que abre el orquestador.

## Cómo debe funcionar
- Corre un `Runtime` real con el cargador del harness: lo que muestra sale del núcleo, no es maqueta.
- Guarda su estado local en `.datos/` (qué está montado, datos de las brigadas, chats y la clave que firma aprobaciones de borradores, protegida con DPAPI en Windows). Nada de eso va a git.
- Sin modelo configurado avisa y no inventa. Las aprobaciones pendientes se aprueban o rechazan desde acá.

## Dónde está hoy
El código vive dentro del harness: `1-harness/b-codigo/panel/`. Se extraerá a esta carpeta cuando se haga el traspaso. Dueña de la pieza: chat 3 (servidor, app e instalador) la hereda como base de la app.
