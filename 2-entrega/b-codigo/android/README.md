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

## Cliente de Raphael personal (25 nov 2026)
La misma app sirve para el servidor de Raphael personal (`raphael_personal_api`, ver `2-entrega/c-despliegue/personal/LEEME.md`): al entrar lee `edition` de `/api/v1/health` y, si es `personal`, muestra otras pestañas: **Hablar** (`/api/v1/chat`), **Decidir** (aprobar, rechazar o resolver; nada se aprueba solo), **Cerebro** (qué modelo usa cada rol y si el local está prendido) y **Ajustes** (claves y roles; los secretos nunca vuelven completos). **Emparejar por QR:** en la página del servidor sale un código de 5 minutos y un QR `raphael://pair?host=…&code=…`; al escanearlo con la cámara se abre la app con el código cargado (la persona confirma con "Emparejar"). Desde afuera de casa el servidor siempre pide clave o código: la app nunca entra sola. Tests: `ModelsTest` (modelos nuevos) y `PersonalContractTest` (contra el servidor real, con `RAPHAEL_PERSONAL_URL` y `RAPHAEL_PERSONAL_KEY`).
Falta: las herramientas del celular para Operaciones (`/ws/phone`) no están en la app; las pantallas nuevas **no se compilaron en la nube** (sin SDK de Android: solo se compilaron y probaron `Api.kt` y `Models.kt` en la JVM) ni se probaron en un teléfono.
