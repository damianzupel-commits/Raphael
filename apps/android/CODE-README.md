# App Android de Raphael Empresas (nativa)

App de la dueña para su Raphael Empresas: Kotlin + Jetpack Compose, sin WebView y sin librerías de terceros para la red (HttpURLConnection + org.json). Habla con la API de la brigada (`..\raphael-empresas-api\API.md`). Hecha en la pieza 15 a pedido de Damián (22 nov 2026).

No tiene lógica de negocio ni guarda datos de clientes: guarda la dirección del servidor y la sesión (el token, nunca la clave), en el almacenamiento privado de la app y fuera de los respaldos. Toda decisión va al servidor y pasa por el Policy Engine del harness.

## Pantallas
- **Hoy:** chat con la Secretaria. Al abrir pide las tareas del día. Cada tarea se puede tocar para ver la ficha (contexto y opciones A/B/C, con la recomendada marcada) y hay sugerencias para tocar. Las órdenes ("aprobá la 2") piden "¿Confirmo?" como en el panel.
- **Decidir:** los pendientes. Para aprobar (presupuesto, seña, turno, cancelación) hay que confirmar en un diálogo que avisa cuando algo no tiene vuelta atrás, y se pueden corregir los campos editables (precio, monto, fecha, hora). Lo humano (reclamos, preguntas sin respuesta) se responde con texto. Desde cada pendiente se puede ver la conversación con el cliente.
- **Encargos:** en curso o todos, con entrega, precio, seña y lo pagado. Para cambiar el estado hay que confirmar, y Avisos le escribe al cliente solo.
- **Agenda:** turnos confirmados por día.
- **Más:** avisos del servidor (resaltados los mensajes que no se pudieron mandar a un cliente), estado de WhatsApp e Instagram (modo prueba o andando, y qué falta), señas esperando y avisadas, preguntas sin responder, estado del catálogo de la tienda, cerrar sesión.
- **Avisos en el celular:** cada ~15 minutos (lo mínimo de Android) consulta `/api/v1/updates` y avisa si hay pendientes nuevos o avisos nuevos (por ejemplo, un mensaje que WhatsApp no dejó mandar fuera de las 24 h). Sin Firebase. Con la app abierta se actualiza sola cada 30 segundos.

## Compilar
Requisitos: JDK 17 o más y el SDK de Android (`platforms;android-35`, `build-tools;35.0.0`), o Android Studio. Poné `sdk.dir=...` en `local.properties` (no se sube a git).
```
gradlew assembleDebug                                  # app/build/outputs/apk/debug/app-debug.apk
gradlew assembleDebug -Pservidor=https://tu-dominio    # con la dirección del servidor precargada
gradlew testDebugUnitTest                              # tests de modelos (7)
gradlew assembleRelease                                # firmado con claves\firma.properties
```
- **Debug** (`com.raphael.empresas.app.debug`) acepta `http://` para probar en la red local. **Release** (`com.raphael.empresas.app`) acepta solo HTTPS.
- **Firma:** `claves\firma.properties` con `archivo`, `alias` y `clave`, y el `.jks` al lado. `claves\` no se sube a git. Las actualizaciones tienen que firmarse con la misma clave. Es un `applicationId` nuevo, distinto del de la app WebView vieja (`com.raphael.empresas`), así que pueden convivir mientras se hace el cambio.

## Probar contra la API de verdad
```
cd ..\raphael-empresas-api
python scripts\servidor_de_prueba.py --port 8799        # instalación de ejemplo, clave "clave-de-prueba"
cd ..\android
set RAPHAEL_API_URL=http://127.0.0.1:8799
gradlew testDebugUnitTest                              # + ApiContractTest: el cliente Kotlin de punta a punta
```

## Estado (23 nov 2026, versión 1.1.0)
- Compila (debug y release sin firmar), lint con 0 errores, pasan los 7 tests de modelos y el test de contrato contra la API real (login, pendientes, aprobar con cambios, resolver, Secretaria, encargos, conversación, canales, avisos, cerrar sesión). Probado en la nube con Gradle 8.14.3, AGP 8.9.1, Kotlin 2.1.10, SDK 35.
- Lint: quedan 7 advertencias a propósito (versiones de dependencias más nuevas, `http` permitido solo en debug, carpeta de íconos `-v26`).
- **No probada en un celular ni en un emulador** (en la nube no hay emulador). Falta probarla a mano en tu teléfono.
- **Pendiente para 03:** push instantáneo (hoy es por consulta periódica) y publicar la API en el VPS con HTTPS.
