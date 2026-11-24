# 2-entrega/b-codigo/android

App nativa de Android: una app, una pestaña por Raphael; el cliente ve solo lo que contrató.

## Cómo debe funcionar
- Se compila con la dirección del servidor fija (`-Pservidor=https://<dominio>`); no se cambia en la app.
- Se firma con la clave de `raphael-android/claves`, que NO va a git y se respalda aparte. Perderla impide actualizar la app instalada.
- Recibe avisos push, muestra las tareas del día y deja aprobar o rechazar lo pendiente.

## Código existente
`raphael\3-mando\c-referencia\servidor-app-installer\raphael-empresas\raphael-android` (versión 0.1.0, sin tests). Pieza dueña: chat 3.

## Código nativo ya hecho (chat 15)
Kotlin + Compose, versión 1.1.0 (avisos, estado de los canales, notificación por avisos, refresco cada 30 s). El APK de debug compila; **no se probó en un teléfono**. El APK no está en git (se compila). `CODE-README.md` es el README del proyecto Gradle. Se conecta a la API de `../server/api/`.
