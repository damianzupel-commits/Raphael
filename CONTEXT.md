# Raphael · contexto del proyecto (leer primero)

Este archivo es el punto de entrada de cualquier chat. Con esto y el README de la rama donde trabajás no hace falta que Damián te pase nada más. Actualizado el 24 nov 2026.

## 1. Qué es Raphael
Asistente con IA de Damián (Rosario, Argentina), en dos ediciones que comparten el mismo núcleo:
- **Personal:** corre solo en su PC, puede tener capacidades peligrosas (pentest, operar la PC y el celular, trading).
- **Empresas:** público, en la nube (VPS), lleva una empresa casi entera con la mínima necesidad de humanos, nunca cero: lo irreversible lo aprueba una persona. Primera clienta: una vendedora de ropa a medida que no tiene PC.

## 2. Arquitectura
- **Harness** (`1-harness/b-codigo`): la base. Contrato versionado, cargador de manifiestos, runtime, bus de eventos, almacén por brigada, Policy Engine con autonomía configurable, modelos por rol, auditoría. No sabe nada de brigadas concretas.
- **Orquestador** (`1-harness/c-brigadas/00-orquestador`): se para sobre el harness. Es el único que habla con la persona. Roles mando, voz y ruteo; reparto por DAG validado por código; confirmación de acciones solo con un "sí" explícito; Secretaria como rol genérico; avisos proactivos.
- **Brigadas** (`1-harness/c-brigadas/*`): se montan y desmontan por configuración sin romper nada. Cada una tiene cocineros (agentes permanentes) y a veces un jefe que lanza efímeros (ayudantes de una tarea).
- **Nadie se habla directo:** ninguna brigada importa a otra; todo pasa por el harness y el orquestador. Un test lo verifica.
- **Despliegues:** Raphael personal = orquestador maestro + todas las brigadas (Empresas es la brigada `business`, con la Secretaria como jefa, y reporta al maestro). Instalación de la clienta = harness + orquestador en modo `secretary` (sin maestro arriba) + brigada `business` + las opcionales que contrate.

## 3. Mapa de carpetas (patrón a/b/c, de a tres)
Cada nivel tiene tres partes: **a** para saber, **b** para hacer y **c** para lo que cuelga de él.
```
raphael/
  CONTEXT.md                 este archivo
  README.md                  el árbol explicado
  1-harness/                 la base: sin harness no corre nada
    a-conocimiento/          spec, diseño, qué se portó y log del harness
    b-codigo/                raphael-core (408 tests) y el panel de escritorio (panel/)
    c-brigadas/              todo lo que se monta sobre el harness
      00-orquestador/        el que habla con la persona y reparte (266 tests)
      05-seguridad/ ... 14-contenido/, 15-empresas/, 16-legales/
        README.md            qué es la brigada y cómo debe funcionar
        a-historia/          cocineros/<cocinero>/README.md, log.md, decisiones
        b-codigo/            manifest.yaml, pyproject.toml, src/
        c-salud/             pruebas/  monitoreo/  mantenimiento/
  2-entrega/                 lo que llega a la gente
    a-conocimiento/          spec y log del servidor, la app y el instalador
    b-codigo/                servidor/ (API, 26 tests), android/, panel-escritorio/
    c-despliegue/            vps/, instalacion-clienta/, cuentas-y-apis/
  3-mando/                   cómo se dirige el proyecto
    a-conocimiento/          ESTADO, PLAN-MAESTRO, PIEZAS, BRIGADAS, SPEC-FAMILIA, log/
    b-herramientas/          gate.bat (puerta de 824 tests + ruff), pruebas-contrato/, pruebas-e2e/
    c-referencia/            código viejo de JarvisRemote y Empresas, solo lectura
  .venv/, .data/             entorno y datos locales, fuera de git
```
Cada carpeta tiene su README: qué es y cómo debe funcionar. Cada cocinero tiene el suyo en `1-harness/c-brigadas/<NN-brigada>/a-historia/cocineros/<cocinero>/README.md`. El log de cada pieza está en su propia rama (`a-historia/log.md` o `a-conocimiento/log.md`).

## 4. Un chat por pieza
| Chat | Pieza | Rama |
| --- | --- | --- |
| 0 | Mando (decisiones y estado) | `3-mando/a-conocimiento/` |
| 1 | Harness | `1-harness/b-codigo` |
| 2 | Orquestador | `1-harness/c-brigadas/00-orquestador` |
| 3 | Servidor, app e instalador | `2-entrega/b-codigo/`, `2-entrega/c-despliegue/` |
| 4 | Cuentas y APIs (Meta, IA, Hetzner, DuckDNS) | operativo, sin claves en el chat |
| 5 a 14 | Seguridad, Antimalware, Investigación, Geolocalización, Memoria·Cerebro, Ingesta, Trading, Operaciones, Autorreparación, Contenido | `1-harness/c-brigadas/<NN-nombre>` |
| 15 | Raphael Empresas | `1-harness/c-brigadas/15-empresas` |
| 16 | Legales | `1-harness/c-brigadas/16-legales` |
| 17 | Revisor (contexto en blanco) | `3-mando/a-conocimiento/log/17-revisor.md` |
Además hay chats de vida (Estudio, Divague, Rutina): sin código ni planes formales salvo que él los pida.

## 5. Reglas de trabajo
- Trabajás solo en tu pieza. Si algo toca otra, anotalo como "pendiente para <pieza>" en su log (`a-historia/log.md` de cada pieza) en vez de resolverlo.
- Código con nombres en inglés; documentación, comentarios de alto nivel y mensajes al usuario en español rioplatense (voseo, directo, corto).
- No leer ni imprimir `.env`, `.env.bak-*` ni claves. Las claves las carga Damián en el servidor; nunca pasan por un chat.
- Los originales (`Documents\raphael`, `Documents\JarvisRemote`) no se tocan. Los push los hace Damián.
- No inventar: si no verificaste algo del código, decilo. Para APIs de Meta, precios o leyes argentinas, buscá la fuente actual.
- Acciones sin vuelta atrás (borrar, mover fuera del proyecto, mandar mensajes, instalar fuera de un entorno virtual): proponelas, no las hagas.
- Cada fase termina con una puerta: un script que corre los tests y sale con código 0 si pasa o 2 si falla. No se pasa a la fase siguiente hasta que dé 0. La del repo es `3-mando\b-herramientas\gate.bat`.
- Al cerrar una sesión: "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió) en `a-historia/log.md` de cada pieza, y actualizar `3-mando/a-conocimiento/ESTADO.md` si cambia algo del proyecto.
- Si el spec se contradice con el código que ya funciona, gana el código; avisá la diferencia.

## 6. Decisiones vigentes
- **Harness v2 (21 nov):** se portaron y unificaron los dos motores (el de Empresas y el de brigadas de JarvisRemote). Raphael Empresas original queda congelado como referencia y sube al VPS por el carril de la brigada nativa.
- **Autonomía:** niveles `automatico`, `aprobacion` y `humano` por acción, configurables por instalación y por brigada, con confianza progresiva. Lo que gasta plata o es irreversible nunca baja solo a automático. El detalle está en `1-harness/a-conocimiento/diseno-harness-v2.md`.
- **Secretaria:** rol genérico del orquestador. En la instalación de la clienta habla con la dueña; en personal es jefa de la brigada Empresas y reporta al maestro.
- **Trading:** toda ejecución, demo o real, requiere aprobación de Damián.
- **Seguridad en la nube:** solo defensiva y pasiva; el pentest activo corre solo en la PC de Damián y nunca en el VPS.
- **Proveedor de IA (24 nov):** NVIDIA para la v1 de Raphael Empresas, vía `NVIDIA_API_KEY`, que el harness ya lee. Sigue configurable por rol y por plan; sin clave el harness degrada a reglas y lo avisa.
- **Modelos sin rechazos (abliterados):** idea en estudio, solo local y solo para Seguridad e Investigación de Raphael personal; nunca en Empresas ni en el orquestador. Sin decisión tomada.
- **Meta:** la v1 sirve a cuentas que administra Damián (acceso estándar). Que cada cliente conecte las suyas exige ser Tech Provider (verificación de empresa y App Review, puede tardar más de 10 días).
- **Hosting:** un VPS en Hetzner (referencia CX33), una instalación por cliente.

## 7. Estado al 24 nov 2026
| Pieza | Estado |
| --- | --- |
| Harness (`1-harness/b-codigo`) | Hecho H1 a H8, contrato 2.1, 408 tests en verde y panel nativo |
| Orquestador | Hechas O1 a O5, 266 tests en verde |
| Empresas (`15-empresas`) | Brigada nativa 2.0.0, 124 tests; API y canal de Meta (26 tests); app Android 1.1.0 (APK compila, sin probar en teléfono); kit del VPS probado solo en modo "solo archivos" |
| Servidor, app e instalador | Falta adoptar la API y el kit, montarlos en el VPS, push |
| Cuentas y APIs | Proveedor de IA: NVIDIA para la v1. Pendiente: VPS en Hetzner, dominio DuckDNS, app de Meta, número de prueba, cuenta de Instagram de prueba |
| Brigadas 05 a 14 y 16 | Solo spec y cocineros definidos; el código existente de JarvisRemote está de referencia en `3-mando/c-referencia/<brigada>/`; Legales es nueva |
Los 824 tests (core 408, orquestador 266, Empresas 124, servidor 26) y ruff pasan en la PC de Damián (Windows, Python 3.12) y en la nube. Falta probar contra Meta real, en un VPS real y la app en un teléfono.

## 8. Cliente de prueba y siguiente paso
Damián le muestra a la clienta la demo de Mi Tienda IA (proyecto aparte, solo demo) para hacerle preguntas; con las respuestas se ajusta Raphael Empresas antes de entregárselo funcionando. Las respuestas van a `1-harness/c-brigadas/15-empresas/INTERVIEW.md` (si no existe, crearlo).

## 9. Riesgos conocidos
- El antimalware de JarvisRemote está sin reglas YARA desde el 24 ago (Windows borró `starter.yar` por contener el texto EICAR).
- Correr `pytest` en JarvisRemote escribe en `backend\data` real: hacerlo solo sobre copias.
- JarvisRemote tiene `.env.bak-*` con claves: no leerlos ni subirlos.
- Video en el VPS de 8 GB: un trabajo a la vez.
- Normas argentinas (Ley 25.326, Ley 24.240, ARCA): verificar con fuente vigente antes de usarlas en Legales.
- Perder la clave de firma de `raphael-android/claves` impide actualizar la app instalada: respaldarla fuera de git.
