# raphael-android

App nativa de **Raphael Empresas** para el celular de la dueña. Es una ventana al panel de *su* Raphael (el que corre
en la mini PC del negocio) con lo que una página web no puede hacer:

- se instala con su ícono (APK) y abre en pantalla completa;
- **avisa en el celular** cuando hay pendientes esperando su decisión (cada ~15 min, sin Firebase ni terceros);
- sube fotos y videos desde la galería (lo va a usar la brigada de Instagram);
- los links a otros sitios (la tienda web, Instagram) se abren afuera, nunca dentro de la app.

No tiene lógica de negocio: todo vive en `raphael-servidor`. La app solo guarda la dirección del servidor y la sesión.

## Cómo funciona
1. Primera vez: pide la dirección del servidor (`192.168.1.50:8787`) y verifica con `/salud` que haya un Raphael.
2. Después abre directo `<servidor>/panel/`. Sin conexión muestra una pantalla para reintentar o cambiar la dirección.
3. El panel le pasa su sesión a la app (`RaphaelApp.guardarToken`) y un servicio (`AvisosWorker`) consulta `/api/pendientes`.

La PC tiene que tener activado **Estado → Conectar el celular** (por defecto Raphael solo escucha en la propia PC).
Fuera de casa hace falta una dirección `https` (túnel o dominio): la app acepta http y https.

## Compilar
Requisitos: JDK 17+ y el SDK de Android (`platforms;android-35`, `build-tools;35.0.0`). Poné `sdk.dir=...` en `local.properties`.

```
./gradlew assembleDebug      # app/build/outputs/apk/debug/app-debug.apk (clave de debug)
./gradlew assembleRelease    # firmado con claves/firma.properties
```

### Firma (importante)
`claves/` **no se sube a git**. Ahí van `raphael-empresas.jks` y `firma.properties` (archivo, alias, clave).
Las actualizaciones de la app tienen que firmarse con la **misma clave**: si la perdés, hay que desinstalar e instalar de cero.
Hacé una copia de `claves/` en un lugar seguro.

## Estructura
- `app/src/main/java/com/raphael/empresas/MainActivity.java` — WebView, puente `RaphaelApp`, navegación, subida de archivos.
- `app/src/main/java/com/raphael/empresas/AvisosWorker.java` — avisos de pendientes en segundo plano.
- `app/src/main/assets/` — pantallas propias: `conectar.html`, `sin-conexion.html`.
- Seguridad: solo las páginas de la app o de *tu* servidor pueden usar el puente `RaphaelApp`.

## Pendiente
- Avisos instantáneos (hoy es por consulta periódica; mejorar con push cuando haya servidor en la nube).
- Publicación en Play Store (hay que pasar a `https` obligatorio y un `applicationId` definitivo).
