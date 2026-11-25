# Plan maestro de Raphael (para el coordinador)

Documento para el coordinador del espacio "raphael" de la app. Está pensado para leerse entero antes de abrir cualquier hilo. Fecha: 24 nov 2026. Si algo de acá contradice a `CONTEXT.md`, manda `CONTEXT.md` y este archivo se corrige.

Orden de lectura: `CONTEXT.md` → este archivo → `3-mando/a-conocimiento/ESTADO.md` → `3-mando/a-conocimiento/PIEZAS.md` → el README de la rama que vayas a tocar.

---

## 1. Qué se está construyendo

Raphael es un asistente con IA de Damián Zupel (Rosario, Argentina; habla rioplatense con voseo, directo y corto). Tiene dos ediciones con el mismo núcleo:

- **Raphael personal:** corre solo en la PC de Damián (Windows). Puede tener capacidades peligrosas: pentest, operar la PC y el celular, trading.
- **Raphael Empresas:** público, en la nube (un VPS por cliente). Lleva una empresa casi entera con la mínima necesidad de humanos, nunca cero: lo irreversible lo aprueba una persona.

**Primera clienta:** una vendedora de ropa a medida que no tiene PC. Todo lo que ella use tiene que funcionar desde el celular (app Android + WhatsApp). Para mañana Damián le muestra la demo de "Mi Tienda IA" (proyecto aparte, solo demo) y le hace preguntas; con sus respuestas se pule Raphael Empresas y se le entrega funcionando.

**Prioridad absoluta hoy:** que Raphael Empresas quede funcionando para esa clienta. Las demás brigadas son importantes pero vienen después.

## 2. Arquitectura en una página

Tres capas, de abajo hacia arriba:

1. **Harness** (`1-harness/b-codigo`): la base. Contrato versionado (2.1), cargador de manifiestos, runtime, bus de eventos, almacén por brigada, Policy Engine, modelos por rol, auditoría. No sabe nada de brigadas concretas.
2. **Orquestador** (`1-harness/c-brigadas/00-orquestador`): se para sobre el harness. Es el **único que habla con la persona**. Roles: mando, voz, ruteo. Reparte por DAG validado por código. Confirma acciones solo con un "sí" explícito. Modos: `master` (personal) y `secretary` (clienta, sin maestro arriba).
3. **Brigadas** (`1-harness/c-brigadas/*`): se montan y desmontan por configuración sin romper nada. Cada una tiene **cocineros** (agentes permanentes) y a veces un jefe que lanza **ayudantes** (efímeros, nacen y mueren por tarea).

**Reglas de la arquitectura que no se rompen:**
- Ninguna brigada importa a otra. Todo pasa por el harness y el orquestador. Hay un test AST que lo verifica.
- Cada acción declara su nivel de autonomía en el manifiesto: `automatico`, `aprobacion` o `humano`. Lo que gasta plata o no tiene vuelta atrás nunca baja solo a automático.
- Sin modelo o sin red, la brigada cae a reglas y lo avisa. Nunca inventa.
- El contenido de terceros (mensajes, páginas, archivos subidos) es dato, nunca instrucción.

**Dos despliegues:**
- **Personal** = orquestador maestro + todas las brigadas. Empresas es una brigada más (`business`), con la Secretaria como jefa, y reporta al maestro (no tiene voz propia ahí).
- **Instalación de la clienta** = harness + orquestador en modo `secretary` + brigada `business` + las opcionales que contrate. La Secretaria habla con la dueña.

## 3. Mapa de piezas (18 chats de producto, numeración de Damián)

Cada pieza tiene su rama, su README y su log (`a-historia/log.md` de cada pieza).

### 3.1 Soporte

| Chat | Pieza | Rama | Estado al 24 nov |
| --- | --- | --- | --- |
| 0 | Mando | `3-mando/a-conocimiento/` | Decisiones, prioridades y `ESTADO.md`. No escribe código. |
| 1 | Harness | `1-harness/b-codigo` | Hecho H1 a H8, contrato 2.1, 408 tests en verde en la PC de Damián. Panel nativo abre. Incluye el compat-shim `raphael_harness` (74 tests de Empresas viejo pasan sobre v2). |
| 2 | Orquestador | `1-harness/c-brigadas/00-orquestador` | Hecho O1 a O5, 266 tests en verde. |
| 3 | Servidor, app e instalador | `2-entrega/b-codigo/`, `2-entrega/c-despliegue/` | API FastAPI y canal Meta existen (26 tests, Meta en modo mock). App Android 1.1.0 (APK compila, **sin probar en teléfono**). Kit del VPS (systemd, Caddy, instalar/actualizar, copia diaria, armado de paquete) probado **solo en modo "solo archivos"**. Falta montarlo en un VPS real. |
| 4 | Cuentas y APIs | operativo | Proveedor de IA elegido: OpenRouter (24 nov; NVIDIA gratis solo desarrollo). Pendiente: VPS Hetzner, DuckDNS, app de Meta, número de prueba, Instagram de prueba. **Nunca recibe claves en el chat.** |

### 3.2 Raphael Empresas (chat 15, `1-harness/c-brigadas/15-empresas`)

Es la única brigada con código nativo y la que usa la clienta. Brigada nativa 2.0.0, 124 tests en verde.

Cocineros (`a-historia/cocineros/`): Secretaria (jefa), Atención (WhatsApp e Instagram, reclamos), Agenda (turnos y recordatorios), Cobros (cobros y deudas), Encargos (pedidos a medida), Avisos (alertas push a la dueña), Tienda (conector de catálogo agnóstico, solo lectura en la v1; adaptador por defecto con feed JSON o CSV; opcionales Tiendanube, Shopify, WooCommerce). En el código hay además un cocinero `tareas` (`owner_tasks`), que usa la Secretaria del orquestador.

Trabajo pendiente de esta pieza:
- Cargar el perfil real de la clienta (`perfil.yaml` → `perfil_a_instalacion.py`).
- Crear `1-harness/c-brigadas/15-empresas/INTERVIEW.md` con las preguntas para la clienta y registrar sus respuestas.
- Revisar el alcance de Tienda.
- Ajustar los módulos según la entrevista.

### 3.3 Brigadas de Raphael personal (chats 5 a 14)

Todas existen en JarvisRemote (código viejo, solo lectura en `3-mando/c-referencia/<brigada>/`). En el repo nuevo tienen README, `a-historia/cocineros/` definidos, y `b-codigo/` y `c-salud/` vacíos. Nada está portado al harness v2. Estado de validación: "sin relevar" salvo donde se indica.

| Chat | Brigada | Cocineros | Dónde corre | Notas clave |
| --- | --- | --- | --- | --- |
| 5 | Seguridad | Auditor de código (defensa), Pentest activo (ataque), Vigilancia defensiva (nuevo) | PC; en el VPS solo defensa pasiva | El pentest activo **nunca** corre en el VPS; un test lo verifica. Objetivos de una lista firmada por Damián. Nunca explota. |
| 6 | Antimalware | Escaneo (YARA, ClamAV, VirusTotal), Vigilancia de procesos, Integridad y cuarentena | PC (Windows); VPS solo revisión pasiva | 13 módulos, 6 dependen de Windows (Sysmon, DPAPI): reemplazar al portar. Sin reglas YARA desde el 24 ago. |
| 7 | Investigación | Forense, Scout, Ideas y prototipos (nuevo), Vigilancia de tendencias (nuevo) | PC hoy; VPS con adaptadores | Nada se afirma sin fuente y fecha. Scout sin validar: necesita `BRAVE_SEARCH_API_KEY`. Prototipos en espacio aislado. |
| 8 | Geolocalización pública | IP e infraestructura (Shodan), Rastreo cripto, Barcos y capas del globo | PC | Solo fuentes públicas, cada resultado con su fuente. |
| 9 | Memoria · Cerebro | Recuperador, Consolidador y destilador, Asociativo/analogías/curiosidad, Proactivo | PC hoy; VPS con vault propio | Última validación real 4/4 (16 nov). Tests de regresión: `test_cerebro_fixes.py` (mezcla de notas) y `test_validation_cerebro.py` (invención). No aflojar criterios. |
| 10 | Ingesta | YouTube, Web, arXiv | PC hoy; VPS sin dependencias de Windows | Toda nota guarda origen (URL y fecha). |
| 11 | Trading | Señales, Backtest, Motor y vigilancia | PC | **Toda ejecución, demo o real, requiere aprobación de Damián.** |
| 12 | Operaciones | PC, Celular, Navegador y web, Supervisor | PC y celular. **Nunca en el VPS** | Las manos de Raphael: autonomía conservadora por defecto. |
| 13 | Autorreparación | Proponer arreglo, Aplicar arreglo (gate y guardarraíl), Introspección | PC | Nada se aplica sin gate, guardarraíl y aprobación. |
| 14 | Contenido | Video (ffmpeg, Whisper), Instagram, Imagen generativa (ComfyUI), Contenido/copys (nuevo), Campañas (nuevo), Analítica (nuevo) | PC hoy; VPS un trabajo de video a la vez | Publicar siempre requiere aprobación. Instagram probado solo con cliente simulado. Marcada "futura" en el Centro de Mando. |

### 3.4 Brigada nueva y control

| Chat | Pieza | Detalle |
| --- | --- | --- |
| 16 | Legales (`1-harness/c-brigadas/16-legales`) | No construida, sin código previo. Cocineros: Documentos, Cumplimiento, Riesgos, Archivo. Corre en el VPS. Argentina. No reemplaza a un abogado; cada afirmación normativa cita fuente oficial y fecha verificada. Normas de partida a verificar: Ley 25.326, Ley 24.240, normativa de facturación de ARCA. |
| 17 | Revisor | Contexto en blanco; revisa cada fase contra `SPEC.md` y deja su informe en `3-mando/a-conocimiento/log/17-revisor.md`. No construye. |

### 3.5 El árbol y las piezas que no son chats numerados

El repo sigue el patrón a/b/c de a tres (ver `README.md` de la raíz): `1-harness/` (a-conocimiento, b-codigo, c-brigadas), `2-entrega/` (a-conocimiento, b-codigo, c-despliegue) y `3-mando/` (a-conocimiento, b-herramientas, c-referencia). Cada brigada, incluido `00-orquestador`, tiene `a-historia/`, `b-codigo/` y `c-salud/` (pruebas, monitoreo, mantenimiento).


- `2-entrega/b-codigo/panel-escritorio`: panel de escritorio (tkinter + Pillow); su código vive en `1-harness/b-codigo/panel/`.
- `2-entrega/c-despliegue/vps`: kit del VPS (pertenece al chat 3).
- `2-entrega/c-despliegue/instalacion-clienta`: `clienta.installation.yaml` y `requirements-vps.txt` (chats 3 y 15).
- `3-mando/b-herramientas/pruebas-contrato` y `3-mando/b-herramientas/pruebas-e2e`: suites transversales.
- `3-mando/b-herramientas/`: scripts y la puerta de calidad `3-mando\b-herramientas\gate.bat` (core 409 + orchestrator 266 + business 124 + server 42 = 841 en verde, ruff limpio).
- `3-mando/a-conocimiento/`: SPEC-FAMILIA, ESTADO, PIEZAS, BRIGADAS, PLAN-MAESTRO y el log del mando y del revisor. Los diseños y logs de cada pieza están en su rama.
- `3-mando/c-referencia/`: código viejo de solo lectura. No se edita.
- Chats de vida (Estudio, Divague, Rutina): no son del producto; sin código ni planes salvo que Damián lo pida.

## 4. Dependencias y camino crítico

```
Cuentas y APIs (4) ──► Servidor/app/instalador (3) ──► Empresas funcionando en el VPS
        │                                                    ▲
        └─ proveedor de IA (OpenRouter, ya elegido)           │
Entrevista a la clienta ──► ajustes en Empresas (15) ────────┘
Harness (1) + Orquestador (2): hechos; las brigadas 5–14 y 16 dependen de ellos.
```

- **Bloqueado por Damián:** el repo privado en GitHub y el push, la IP del VPS, el subdominio DuckDNS, la app de Meta con número de prueba, la clave de NVIDIA cargada en el servidor, las respuestas de la clienta.
- **Se puede avanzar ya sin él:** `INTERVIEW.md`, ajustes en Empresas, revisión de Tienda, preparación del kit del VPS, preparación de las brigadas siguientes.
- Las brigadas 5–14 y 16 son **independientes entre sí**: se pueden portar en cualquier orden y en paralelo, siempre que cada hilo toque su rama.

## 5. Cómo lanzar los hilos

**Máximo 4 en paralelo.** Cada hilo es una sesión completa y gasta el plan de Damián. Nunca dos hilos sobre la misma rama. Antes de abrir cada tanda, decile a Damián qué hace cada hilo y esperá su OK.

### Tanda 1 (ahora)
1. **Empresas (15):** pulir para la clienta; `INTERVIEW.md`; perfil real; revisar Tienda.
2. **Servidor, app e instalador (3):** adoptar la API y el kit, preparar el montaje en el VPS (bloqueado en la parte real hasta tener IP y dominio).
3. **Cuentas y APIs (4):** guiar a Damián en Hetzner, DuckDNS, Meta y la carga de claves. Sin claves en el chat.
4. **Revisor (17):** revisión en blanco del estado actual contra `SPEC.md` y los 824 tests.

### Tandas siguientes (una por vez, cuando la anterior cierre)
- **Tanda 2 (base que usan las demás):** Memoria·Cerebro (9), Ingesta (10), Operaciones (12), Autorreparación (13).
- **Tanda 3:** Seguridad (5), Antimalware (6), Investigación (7), Geolocalización (8).
- **Tanda 4:** Trading (11), Contenido (14), Legales (16).

Si Damián pide otro orden, gana lo que él diga.

### Plantilla de arranque para cada hilo
> Pieza: <chat y nombre>. Rama: <ruta>. Leé `CONTEXT.md`, `3-mando/a-conocimiento/ESTADO.md`, el README de tu rama, los README de tus cocineros (`a-historia/cocineros/`) y tu log (`a-historia/log.md`). Trabajá solo en tu rama; el código viejo está en `3-mando/c-referencia/<brigada>/` (solo lectura). Portá los cocineros al harness v2 (código en `b-codigo/`, tests en `c-salud/pruebas/`): manifiesto válido, healthcheck, montar y desmontar, sin imports de otras brigadas, acciones con su nivel de autonomía. Tests en verde y ruff limpio. Al cerrar: "Resumen de cierre" de 3 a 6 líneas en `a-historia/log.md`. Si algo toca otra pieza, anotalo como "pendiente para <pieza>".

## 6. Criterios de "hecho" (para toda brigada)

- Pasa la suite de contrato del harness v2 (`run_contract_suite`): manifiesto válido, healthcheck, montar y desmontar.
- Ningún import de otra brigada (chequeo AST).
- Los tests existentes de la brigada se portan y pasan.
- Las acciones con efecto no se ejecutan sin su nivel de autonomía.
- La puerta de la fase (`3-mando\b-herramientas\gate.bat` o la de la pieza) sale con código 0. Con código 2 no se pasa a la fase siguiente.
- Ruff limpio.
- "Resumen de cierre" en su log y `ESTADO.md` actualizado por el coordinador.

**Verificá siempre.** Si un hilo dice que algo anda, confirmá que corrió los tests antes de darlo por hecho. "Sin probar" no es "hecho".

## 7. Decisiones vigentes (no se reabren sin que Damián lo pida)

- Harness v2 unificó los dos motores. Raphael Empresas original queda congelado como referencia.
- Autonomía configurable por acción, por instalación y por brigada, con confianza progresiva.
- Secretaria: rol genérico del orquestador (habla con la dueña en la clienta; en personal reporta al maestro).
- Trading: toda ejecución con aprobación.
- Seguridad en la nube: solo defensiva y pasiva. El pentest activo solo en la PC.
- Proveedor de IA para la v1 de Empresas: OpenRouter (`OPENROUTER_API_KEY`), DeepSeek V4 Flash de principal y modelos `:free` rotando en roles chicos, con `data_collection=deny`. NVIDIA gratis solo para desarrollo (sus términos no permiten producción). Detalle en `CONTEXT.md` §6. Sin clave, el harness degrada a reglas y lo avisa.
- Modelos sin rechazos (abliterados): idea en estudio, solo local y solo para Seguridad e Investigación de personal. Nunca en Empresas ni en el orquestador. Sin decisión.
- Meta: la v1 sirve a cuentas que administra Damián. Que cada cliente conecte las suyas exige ser Tech Provider (verificación de empresa y App Review, puede tardar más de 10 días).
- Hosting: un VPS por cliente en Hetzner (referencia CX33, 4 vCPU, 8 GB, Ubuntu 24.04), dominio con DuckDNS, webhook `/webhook/meta` con HTTPS.
- Idioma: nombres de código en inglés; documentación y mensajes al usuario en español rioplatense.
- Los planes viejos **no se usan**: el plan P0 a P6 y el brief de Fable 5.2 son de JarvisRemote y están en gran parte superados por el harness v2 y el orquestador. La sugerencia "Arrancar la etapa P0" está desactualizada.

## 7 bis. Decisiones que le tocan a Damián (preguntale, no asumas)

- ~~Confirmar el proveedor de IA~~ decidido el 24 nov: OpenRouter. Falta verificar slugs y precios de los modelos.
- Hosting definitivo y plan del VPS.
- Qué brigadas opcionales contrata la clienta además de `business`.
- Orden de las tandas 2 a 4.
- Cualquier cosa que gaste plata, publique, envíe mensajes o borre.

## 8. Lo que solo puede hacer Damián

1. Crear el repo privado vacío `raphael` en GitHub (sin README) y hacer el push desde `D:\Raphael Ultimate\raphael`:
   `git remote add origin https://github.com/damianzupel-commits/raphael.git` y `git push -u origin main`.
2. Crear el VPS en Hetzner y pasar **solo la IP** (nunca la contraseña).
3. Crear el subdominio en DuckDNS apuntado a esa IP.
4. En developers.facebook.com: app Business, WhatsApp, número de prueba; cuenta de Instagram de prueba.
5. Cargar `OPENROUTER_API_KEY` en el servidor.
6. Compilar el APK con `-Pservidor=https://<dominio>` y probarlo en un teléfono.
7. Respaldar la clave de firma de Android (`raphael-android/claves`) **fuera de git**. Perderla impide actualizar la app ya instalada.
8. Borrar a mano la basura de `_archivo` (`_para_borrar`, `Claude outputs`, `obra\tmp-*`).
9. Hacer todos los push.

## 9. Reglas fijas para todos los hilos

- Trabajar solo en `D:\Raphael Ultimate\raphael`. Los originales (`Documents\raphael`, `Documents\JarvisRemote`) no se tocan.
- No leer ni imprimir `.env`, `.env.bak-*` ni claves. Las claves las carga Damián en el servidor.
- Los push los hace Damián.
- Acciones sin vuelta atrás (borrar, mover fuera del proyecto, mandar mensajes, instalar fuera de un entorno virtual): proponerlas, no hacerlas.
- No inventar. Si algo no se verificó, decirlo. Para APIs de Meta, precios o leyes argentinas, buscar la fuente actual.
- Si el spec contradice al código que ya funciona, gana el código; avisar la diferencia.
- Correr `pytest` de JarvisRemote solo sobre copias: escribe en `backend\data` real.
- Video en el VPS de 8 GB: un trabajo a la vez.

## 10. Riesgos y cosas sin verificar

- **Sin probar todavía:** la app Android en un teléfono, el canal contra Meta real (solo mock), el kit en un VPS real, Scout (falta clave de Brave), la validación de la mayoría de las brigadas personales.
- Antimalware sin reglas YARA desde el 24 ago (Windows borró `starter.yar` por contener texto EICAR).
- `.env.bak-*` de JarvisRemote contienen claves: no leerlos ni subirlos. `.gitignore` ya excluye `.data/`, `.venv/`, `dist/`, `claves/`, `*.sqlite`, `*.apk`.
- Normas argentinas (Ley 25.326, Ley 24.240, ARCA): verificar con fuente vigente antes de usarlas.
- Sin verificar: los ayudantes de cada brigada personal (solo se conocen los de Investigación) y las brigadas del Raphael viejo con la bolita flotante.
- Tech Provider de Meta puede demorar más de 10 días: no prometer a clientes masivos antes.
- Límite de uso: cada hilo cuenta como sesión completa. Si el plan se agota, bajar el paralelismo.

## 11. Qué debe hacer el coordinador ahora

1. Leer este documento, `CONTEXT.md`, `ESTADO.md` y `PIEZAS.md`.
2. Proponerle a Damián la tanda 1 con un renglón por hilo y esperar su OK.
3. Abrir los hilos aprobados (máximo 4).
4. Al cerrar cada uno: verificar los tests, actualizar `ESTADO.md` y proponer la tanda siguiente.
5. Mantener este archivo al día cuando cambie una decisión o el orden.
