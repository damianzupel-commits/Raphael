# Raphael · contexto del proyecto (leer primero)

Este archivo es el punto de entrada de cualquier chat. Con esto y el README de la rama donde trabajás no hace falta que Damián te pase nada más. Actualizado el 24 nov 2026.

## 1. Qué es Raphael
Asistente con IA de Damián (Rosario, Argentina), en dos ediciones que comparten el mismo núcleo:
- **Personal:** corre solo en su PC, puede tener capacidades peligrosas (pentest, operar la PC y el celular, trading).
- **Empresas:** público, en la nube (VPS), lleva una empresa casi entera con la mínima necesidad de humanos, nunca cero: lo irreversible lo aprueba una persona. Primera clienta: una vendedora de ropa a medida que no tiene PC.

## 2. Arquitectura
- **Harness** (`packages/core`): la base. Contrato versionado, cargador de manifiestos, runtime, bus de eventos, almacén por brigada, Policy Engine con autonomía configurable, modelos por rol, auditoría. No sabe nada de brigadas concretas.
- **Orquestador** (`packages/orchestrator`): se para sobre el harness. Es el único que habla con la persona. Roles mando, voz y ruteo; reparto por DAG validado por código; confirmación de acciones solo con un "sí" explícito; Secretaria como rol genérico; avisos proactivos.
- **Brigadas** (`brigades/*`): se montan y desmontan por configuración sin romper nada. Cada una tiene cocineros (agentes permanentes) y a veces un jefe que lanza efímeros (ayudantes de una tarea).
- **Nadie se habla directo:** ninguna brigada importa a otra; todo pasa por el harness y el orquestador. Un test lo verifica.
- **Despliegues:** Raphael personal = orquestador maestro + todas las brigadas (Empresas es la brigada `business`, con la Secretaria como jefa, y reporta al maestro). Instalación de la clienta = harness + orquestador en modo `secretary` (sin maestro arriba) + brigada `business` + las opcionales que contrate.

## 3. Mapa de carpetas
```
raphael/
  CONTEXT.md        este archivo
  README.md         qué es cada cosa de esta carpeta
  apps/             desktop-panel, android, server (con api/)
  packages/         core (harness), orchestrator
  brigades/         security, antimalware, research, geo-intel, memory, ingestion,
                    trading, operations, self-repair, content, business, legal
  docs/             SPEC-FAMILIA, ESTADO, PIEZAS, BRIGADAS, design/, log/
  infra/            cloud/ (kit del VPS), client-install/ (instalación de la clienta)
  _reference/       código existente de JarvisRemote y Empresas viejo, solo lectura
  tests/            contract/, e2e/
  tools/            scripts y puertas de fase
  .data/            datos locales, fuera de git
```
Cada rama tiene su README: qué es y cómo debe funcionar. Cada cocinero tiene el suyo en `brigades/<brigada>/cooks/<cocinero>/README.md`.

## 4. Un chat por pieza
| Chat | Pieza | Rama |
| --- | --- | --- |
| 0 | Mando (decisiones y estado) | `docs/` |
| 1 | Harness | `packages/core` |
| 2 | Orquestador | `packages/orchestrator` |
| 3 | Servidor, app e instalador | `apps/`, `infra/` |
| 4 | Cuentas y APIs (Meta, IA, Hetzner, DuckDNS) | operativo, sin claves en el chat |
| 5 a 14 | Seguridad, Antimalware, Investigación, Geolocalización, Memoria·Cerebro, Ingesta, Trading, Operaciones, Autorreparación, Contenido | `brigades/<nombre>` |
| 15 | Raphael Empresas | `brigades/business` |
| 16 | Legales | `brigades/legal` |
| 17 | Revisor (contexto en blanco) | `docs/log/reviewer.md` |
Además hay chats de vida (Estudio, Divague, Rutina): sin código ni planes formales salvo que él los pida.

## 5. Reglas de trabajo
- Trabajás solo en tu pieza. Si algo toca otra, anotalo como "pendiente para <pieza>" en su log (`docs/log/<pieza>.md`) en vez de resolverlo.
- Código con nombres en inglés; documentación, comentarios de alto nivel y mensajes al usuario en español rioplatense (voseo, directo, corto).
- No leer ni imprimir `.env`, `.env.bak-*` ni claves. Las claves las carga Damián en el servidor; nunca pasan por un chat.
- Los originales (`Documents\raphael`, `Documents\JarvisRemote`) no se tocan. Los push los hace Damián.
- No inventar: si no verificaste algo del código, decilo. Para APIs de Meta, precios o leyes argentinas, buscá la fuente actual.
- Acciones sin vuelta atrás (borrar, mover fuera del proyecto, mandar mensajes, instalar fuera de un entorno virtual): proponelas, no las hagas.
- Cada fase termina con una puerta: un script que corre los tests y sale con código 0 si pasa o 2 si falla. No se pasa a la fase siguiente hasta que dé 0.
- Al cerrar una sesión: "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió) en `docs/log/<pieza>.md`, y actualizar `docs/ESTADO.md` si cambia algo del proyecto.
- Si el spec se contradice con el código que ya funciona, gana el código; avisá la diferencia.

## 6. Decisiones vigentes
- **Harness v2 (21 nov):** se portaron y unificaron los dos motores (el de Empresas y el de brigadas de JarvisRemote). Raphael Empresas original queda congelado como referencia y sube al VPS por el carril de la brigada nativa.
- **Autonomía:** niveles `automatico`, `aprobacion` y `humano` por acción, configurables por instalación y por brigada, con confianza progresiva. Lo que gasta plata o es irreversible nunca baja solo a automático. El detalle está en `docs/design/harness-v2.md`.
- **Secretaria:** rol genérico del orquestador. En la instalación de la clienta habla con la dueña; en personal es jefa de la brigada Empresas y reporta al maestro.
- **Trading:** toda ejecución, demo o real, requiere aprobación de Damián.
- **Seguridad en la nube:** solo defensiva y pasiva; el pentest activo corre solo en la PC de Damián y nunca en el VPS.
- **Proveedor de IA:** sin decidir; el harness lo deja configurable por rol y por plan. Hoy el harness lee `NVIDIA_API_KEY` en pruebas y sin clave degrada a reglas y lo avisa.
- **Modelos sin rechazos (abliterados):** idea en estudio, solo local y solo para Seguridad e Investigación de Raphael personal; nunca en Empresas ni en el orquestador. Sin decisión tomada.
- **Meta:** la v1 sirve a cuentas que administra Damián (acceso estándar). Que cada cliente conecte las suyas exige ser Tech Provider (verificación de empresa y App Review, puede tardar más de 10 días).
- **Hosting:** un VPS en Hetzner (referencia CX33), una instalación por cliente.

## 7. Estado al 24 nov 2026
| Pieza | Estado |
| --- | --- |
| Harness (`core`) | Hecho H1 a H8, contrato 2.1, 405 tests en verde (en la nube) y panel nativo |
| Orquestador | Hechas O1 a O5, 266 tests en verde |
| Empresas (`business`) | Brigada nativa 2.0.0, 124 tests; API y canal de Meta (26 tests); app Android 1.1.0 (APK compila, sin probar en teléfono); kit del VPS probado solo en modo "solo archivos" |
| Servidor, app e instalador | Falta adoptar la API y el kit, montarlos en el VPS, push |
| Cuentas y APIs | Pendiente: VPS en Hetzner, dominio DuckDNS, app de Meta, número de prueba, cuenta de Instagram de prueba, proveedor de IA |
| Brigadas 05 a 14 y 16 | Solo spec y cocineros definidos; el código existente de JarvisRemote está de referencia en `_reference/<brigada>/`; Legales es nueva |
Nada de esto se probó todavía en la PC de Damián con Python de Windows (los tests corrieron en la nube con Python 3.12 y 3.13), ni contra Meta real, ni en un VPS real.

## 8. Cliente de prueba y siguiente paso
Damián le muestra a la clienta la demo de Mi Tienda IA (proyecto aparte, solo demo) para hacerle preguntas; con las respuestas se ajusta Raphael Empresas antes de entregárselo funcionando. Las respuestas van a `brigades/business/INTERVIEW.md` (si no existe, crearlo).

## 9. Riesgos conocidos
- El antimalware de JarvisRemote está sin reglas YARA desde el 24 ago (Windows borró `starter.yar` por contener el texto EICAR).
- Correr `pytest` en JarvisRemote escribe en `backend\data` real: hacerlo solo sobre copias.
- JarvisRemote tiene `.env.bak-*` con claves: no leerlos ni subirlos.
- Video en el VPS de 8 GB: un trabajo a la vez.
- Normas argentinas (Ley 25.326, Ley 24.240, ARCA): verificar con fuente vigente antes de usarlas en Legales.
- Perder la clave de firma de `raphael-android/claves` impide actualizar la app instalada: respaldarla fuera de git.
