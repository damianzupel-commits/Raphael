# Registro · 17 · Revisor

Revisiones de fase con contexto en blanco.

## 24 nov 2026 · Revisión en blanco del estado contra SPEC y tests
Revisor sin contexto previo. No se construyó nada: solo se leyó (CONTEXT, ESTADO, PLAN-MAESTRO, PIEZAS, los SPEC de harness, entrega y cuentas, el README de Empresas, `modelos.yaml`, `policy.py`, los tests de puerta) y se corrió la puerta sobre `main` (commit `6d4f614`) en la nube, Python 3.13, con `pip install -e` de las cuatro piezas.

### Veredicto
El código cumple lo que ESTADO dice de él. Lo que está desactualizado es la documentación y hay dos riesgos de decisión que conviene mirar antes de entregar a la clienta.

### 1. Lo verificado (coincide con ESTADO)
- `gate.py` da EN VERDE: core 405, orchestrator 266, business 124, server 26 = **821 passed, 0 failed**, ruff limpio. Los números de CONTEXT y ESTADO son reales (corrida propia, no copiada).
- Criterios de aceptación del SPEC del harness:
  - Suite de contrato (manifiesto, healthcheck, montar/desmontar): `test_suite_de_contrato` corre `run_contract_suite` sobre la brigada real de Empresas en `personal` y `cloud`. Cumple.
  - Ninguna acción con efecto sin su nivel: `15-empresas/c-salud/pruebas/test_gate.py` cruza cada `Action(...)` del código con el manifiesto y comprueba que las no automáticas quedan pendientes. Cumple.
  - Lo irreversible no baja solo a automático: está en `policy.py` y en `test_gate.py` (d). Cumple.
- El servidor guarda solo hash de la clave de la dueña (PBKDF2) y del token, con bloqueo por intentos fallidos. Sin secretos en el repo: no hay claves en archivos versionados (búsqueda de patrones de claves conocidos), solo plantillas `*.env.plantilla`; `.gitignore` cubre `.env*`, claves, `.apk`, bases.

### 2. Desvíos entre documentos y código (para corregir)
1. `1-harness/a-conocimiento/SPEC.md` dice "Harness v2 sin empezar" y "proveedor de IA sin decidir": el harness está en H1 a H8 y el proveedor es NVIDIA. También cita "los 21 tests de raphael-harness" como vara mínima, hoy son 405 propios más los 74 de compat.
2. `2-entrega/a-conocimiento/SPEC-servidor-app-instalador.md` dice "Servidor 0.4.0 (28 tests)... VPS aún sin crear"; el código nuevo tiene 26 tests y el servidor es otro paquete (`raphael_empresas_api`). El número 28 es del servidor viejo.
3. `2-entrega/c-despliegue/cuentas-y-apis/SPEC.md` aún dice "elegir proveedor de IA" (ya elegido el 24 nov).
4. `15-empresas/README.md` §Estado dice "116 tests" y rutas viejas (`codigo/raphael-empresas`, `codigo/instalacion`, `DISENO.md §7-9`); hoy son 124 tests y el árbol a/b/c.
5. SPEC del harness: "Políticas sin pisos fijos... cualquier acción puede bajarse hasta automático" frente a CONTEXT §6 y `policy.py`: "lo que gasta plata o es irreversible nunca baja solo a automático". No es contradicción real (bajar es posible con `confirmed_by`, no automáticamente), pero el SPEC debería decirlo con esas palabras. Según la regla de CONTEXT §5, gana el código.
6. `INTERVIEW.md` de Empresas figura como pendiente en ESTADO y PLAN-MAESTRO y no existe; tampoco hay perfil real de la clienta cargado.

### 3. Huecos de verificación
- **Imports cruzados entre brigadas:** `test_ast_imports.py` prueba el detector con paquetes de juguete. La comprobación sobre código real está en la suite de contrato por brigada, y de las 13 carpetas de brigada solo Empresas tiene `manifest.yaml` y código. El orquestador (0 manifests, 17 archivos) no pasa por esa suite; no encontré un test que verifique que ni el orquestador ni Empresas se importan entre sí. A mano, grep no muestra imports cruzados; falta el test que lo fije.
- **Sin probar en entorno real:** Meta real (la API corre en modo mock), VPS real (kit probado solo en "solo archivos"), app Android en teléfono, DPAPI en Windows (HMAC de borradores), síntesis con NVIDIA real. ESTADO lo admite; lo repito porque es lo que separa "821 verdes" de "funciona para la clienta".
- Los 821 tests son unitarios y de integración con mocks; `pruebas-contrato/` y `pruebas-e2e/` de 3-mando/b-herramientas tienen solo README.
- Brigadas 05 a 14 y 16: 0 archivos Python y 0 manifests. Coincide con ESTADO ("solo spec y cocineros").

### 4. Riesgos de decisión
1. **NVIDIA en producción con clientes.** `modelos.yaml` advierte que el acceso gratis de build.nvidia.com se plantea para desarrollo y pruebas, no producción, y que había que verificar los términos antes de usarlo con clientes. CONTEXT lo fijó como proveedor de la v1 el 24 nov sin registrar esa verificación. Además los mensajes de los clientes de la clienta saldrían a un proveedor externo: conviene decirlo en Legales (Ley 25.326, a verificar con fuente vigente).
2. **Escalón `local` apunta a NVIDIA** en `modelos.yaml`. Está documentado y la privacidad se decide por dirección y no por nombre, pero hoy "lo privado" (`memoria-cerebro`, `investigacion-forense`) simplemente no tiene modelo y cae a reglas. Es lo correcto, pero no hay aviso visible al usuario más que el degradado.
3. `LOOPBACK` en `models/config.py` incluye `0.0.0.0`; no es una dirección local (es "todas las interfaces"). Bajo impacto, pero un endpoint configurado así se trataría como privado.
4. Meta: la v1 depende de cuentas administradas por Damián; Tech Provider puede tardar más de 10 días (CONTEXT §6). Es el camino crítico si la clienta quiere conectar sus propias cuentas.

### 5. Recomendaciones (en orden)
1. Corregir los desvíos 1 a 4 de §2 (documentación, sin tocar código) para que SPEC y ESTADO digan lo mismo.
2. Agregar un test de imports cruzados sobre el árbol real (orquestador, Empresas, servidor).
3. Decidir y anotar en CONTEXT §6: términos de NVIDIA para producción, o plan B de proveedor antes de entregar.
4. Crear `INTERVIEW.md` y cargar el perfil de la clienta (bloquea ajustar Empresas).
5. Antes de la clienta: una corrida e2e real (VPS + Meta de prueba + app en teléfono); hoy es el mayor riesgo y nada de lo verde lo cubre.

### Resumen de cierre
- Se revisó el repo en blanco contra SPEC, ESTADO y tests; puerta EN VERDE con 821 tests, igual a lo declarado.
- Se encontraron 6 desvíos de documentación, 1 hueco de test (imports cruzados sobre código real) y 4 riesgos de decisión (el principal, NVIDIA gratis en producción).
- No se tocó código ni otros documentos. Queda a Damián decidir qué se corrige y en qué hilo.

---

## 25 nov 2026 · Segunda revisión: estado de `main` antes de la tanda de brigadas en paralelo
Revisor sin contexto previo sobre la conversación; leí `CONTEXT.md`, `ESTADO.md`, `PLAN-MAESTRO.md`, `PIEZAS.md`, el informe anterior y el código que cambió desde entonces (servidor, `entorno.py`, `configuracion.py`, `is_same_pc`). Corrí la puerta sobre `main` (`e616333`) en la nube, Python 3.13, venv aparte con `pip install -e` de las cuatro piezas. No se construyó nada ni se tocó código; solo se agregó este informe.

### Veredicto
`main` está sano y los desvíos 1 a 6 del informe del 24 nov quedaron cerrados. Hay dos cosas que conviene resolver **antes de que entren los pull requests de las brigadas nuevas**, porque si no la puerta en verde no las va a cubrir (§3), y una decisión de seguridad que Damián debería conocer (§4).

### 1. Verificado
- Puerta EN VERDE: core 409, orchestrator 266, business 124, server **51** = **850 passed, 0 failed**, ruff limpio. ESTADO dice 841 (server 42): el server tiene 9 tests más que lo escrito (los de configuración web). Corregir el número en ESTADO.
- Desvíos del informe anterior: SPEC del harness, SPEC de entrega, SPEC de cuentas y README de Empresas ya dicen lo mismo que el código; `INTERVIEW.md` existe; el test de imports cruzados sobre código real existe (`test_imports_codigo_real.py`).
- Sin secretos versionados: búsqueda de patrones de claves (OpenRouter, NVIDIA, AWS, Meta, GitHub) solo encuentra datos falsos en un test y texto en `INVENTARIO-FASE0.md`; los únicos `.env*` versionados son tres `*.plantilla`.
- Acceso sin clave desde la PC (`RAPHAEL_LOCAL_SIN_CLAVE=1`): `is_same_pc` exige cliente 127.0.0.1/::1, ningún encabezado de reenvío o de Tailscale, `Host` local y `Origin`/`Sec-Fetch-Site` coherentes. Con Funnel, el `Host` llega como el nombre `ts.net`, así que falla la comprobación fuerte y se pide clave. Lo leí; no lo probé contra un Funnel real.

### 2. Reglas que no se tocan: qué hay que mirar en cada PR de la tanda
Hoy solo Empresas tiene código, así que estas reglas todavía no se pueden verificar en las otras brigadas. Lista para revisar cada PR (marcar cada punto con evidencia, no con "parece que sí"):
1. **Manifiesto**: cada acción con efecto tiene su nivel; las que gastan plata, publican, mandan mensajes o borran no son `automatico`. Hay un test que cruza las `Action(...)` del código con el manifiesto (modelo: `15-empresas/c-salud/pruebas/test_gate.py`).
2. **Trading**: ninguna ruta llega a ejecutar una orden, ni en demo ni contra el simulado, sin pasar por aprobación de Damián. Buscar un test que intente ejecutar y verifique que queda pendiente.
3. **Pentest activo** (Seguridad): solo con modo `personal`; la brigada no debe montarse con `cloud` ni en `secretary`. Buscar el test que lo prueba.
4. **Ninguna brigada importa a otra** y el test corre sobre el código real de esa brigada.
5. **Enchufable**: adaptador real y simulado; los tests corren con el simulado y no tocan red ni claves; sin clave cae a reglas y lo avisa (no falla en silencio).
6. **Claves**: solo variables de entorno; `.env.plantilla` con nombres y sin valores; ningún `.env*` ni clave versionada.
7. **Lo sensible no sale a la nube** (decisión del 25 nov): Seguridad, Investigación, Memoria y Operaciones usan modelo local; si el local no está prendido, avisan y no mandan nada a la nube. Buscar el test de ese caso.
8. **Datos que faltan** de la pieza están en su `.env.plantilla` y pasados al coordinador para `LIENZO-DAMIAN.md`.
9. **Salud**: `health` real (no un `return True`), montar/desmontar, suite de contrato en verde, "Resumen de cierre" en el log.

### 3. Huecos (resolver antes de mergear las brigadas)
1. **La puerta no cubre brigadas nuevas.** `gate.py` tiene `SUITES` fijas (core, orchestrator, business, server). Una brigada con tests rojos o sin tests no cambia el resultado de la puerta. Cada brigada que se sume necesita su entrada en `SUITES` y en `RUFF_PATHS`. `gate.py` es del coordinador: se lo paso.
2. **El test de imports cruzados también es una lista fija** (`PAQUETES` y `PROHIBIDOS` en `test_imports_codigo_real.py`): una brigada nueva no queda vigilada hasta que alguien la agregue. Mejor que descubra los paquetes por `manifest.yaml` y prohíba cualquier `raphael_*` que no sea el harness (o el propio). Es del harness; queda como pendiente para esa pieza o para el coordinador.
3. **Dos `manifest.yaml` en Empresas** (`b-codigo/manifest.yaml` y `b-codigo/src/raphael_empresas/manifest.yaml`). Hay que confirmar cuál lee el harness y si el segundo es copia del paquete; si divergen, uno miente. Pendiente para Empresas.
4. Sin cambios desde el informe anterior: `pruebas-contrato/` y `pruebas-e2e/` solo tienen README. Con 13 brigadas nuevas, la prueba e2e (mensaje, encargo, aprobación) sigue sin existir como test automático.

### 4. Riesgos de decisión
1. **El acceso sin clave desde la PC aprueba lo irreversible.** Cualquier proceso de esa PC que hable con `127.0.0.1` con un `Host` local puede aprobar acciones pendientes de la dueña sin clave (el código frena a páginas web ajenas, no a otros programas). Es una decisión consciente y la defensa está bien armada; solo hay que saber que "aprobación humana" depende ahí de la seguridad de la PC. Conviene que las acciones nivel `humano` sigan pidiendo la clave aunque `local_open` esté activo (no verifiqué si ya lo hacen).
2. **`/config` visible por el túnel**: ya está en ESTADO. Pide clave y limita intentos; con clave inicial en `.data/empresas/clave-inicial.txt` hasta que se cambie, conviene que el chequeo de arranque avise si sigue sin cambiarse.
3. `LOOPBACK` en `models/config.py` sigue incluyendo `0.0.0.0` (informe anterior, riesgo 3): un endpoint configurado así se trataría como privado. Pendiente para el harness.
4. Supuestos sin verificar de OpenRouter (slugs, precios, tope de USD 5, retención por proveedor): están marcados en CONTEXT §6; ninguno está probado con clave real.
5. **Meta real, VPS real, app en teléfono, Windows**: sin probar. Sigue siendo lo que separa "850 verdes" de "funciona para la clienta". Además ESTADO anota un test de permisos 600 de `raphael.env` que falla en Windows (la puerta de Windows no se corrió con el cambio más nuevo).

### Pendiente para el coordinador (archivos compartidos)
- `ESTADO.md`: server 51 tests y puerta 850 (hoy 42 y 841); anotar este informe en "Cambios recientes".
- `gate.py`: sumar cada brigada nueva a `SUITES` y `RUFF_PATHS` a medida que entra.
- Nota para el harness/coordinador: volver dinámico el test de imports cruzados (§3.2).

### Resumen de cierre
- Revisé `main` (`e616333`) en blanco: puerta EN VERDE con 850 tests, ruff limpio, sin secretos versionados, y los 6 desvíos del 24 nov cerrados.
- Encontré 4 huecos (la puerta y el test de imports no cubren brigadas nuevas, dos manifiestos en Empresas, e2e sin automatizar) y 5 riesgos de decisión; el que más importa es que el acceso sin clave desde la PC permite aprobar lo irreversible.
- Dejé la lista de 9 puntos para revisar cada PR de la tanda (§2). No construí nada ni toqué archivos compartidos.
- Cuando entren los PR de las brigadas, los reviso contra esa lista y agrego un informe por tanda en este mismo log.

---

## 25 nov 2026 · Tercera revisión: tanda de brigadas (PR 12 a 26, integrados en el PR 27) y PR 28
Revisor en blanco. Revisé el árbol del PR 27 (`e9c0962`, integra las 16 piezas) y el diff del PR 28 (`f412e8b`). Corrí la puerta en la nube (Python 3.13, venv aparte): **EN VERDE, 1872 passed, 0 failed, ruff limpio** (core 430, orquestador 290, Empresas 141, servidor 97, seguridad 62, antimalware 83, investigación 68, geolocalización 88, memoria 149, ingesta 73, trading 59, operaciones 96, autorreparación 106, contenido 54, legales 54, cuentas 22): coincide con lo declarado. Revisé el conjunto contra la lista de 9 puntos, no cada PR línea por línea; los hallazgos por pieza se ven en el PR 27 porque contiene a todos. El PR 28 se fusiona sin conflictos sobre el 27 (probado, sin commitear).

### Veredicto
Lo estructural está bien hecho y se puede mergear en el orden 12 a 26, luego 27 y 28, **después de corregir A1 y A2**. El resto son avisos.

### Cumplen (con evidencia)
1. **Puerta**: `gate.py` corre las 16 suites; una brigada roja tumba la puerta. Resuelto el hueco del informe anterior.
2. **Imports cruzados**: `test_imports_codigo_real.py` descubre las brigadas por `b-codigo/src/*` y las vigila a todas. Resuelto.
3. **Trading**: `ejecutar_orden` y `cerrar_posicion` en `aprobacion` con `spend` e `irreversible`; además `_guard_never_automatic` corta aunque la instalación diga `automatico` (tests `test_aunque_la_instalacion_diga_automatico...` y `test_sin_confirmacion_el_harness_no_baja_a_automatico`). Cuenta real exige `TRADING_ALLOW_LIVE=1`; en paper rechaza cuentas que no empiecen con `DU`. Edición solo `personal`.
4. **Pentest activo**: `ensure_local_edition` lo corta fuera de `personal` (Seguridad se monta también en `cloud`, pero solo en modo pasivo; el estado lo dice). Tests en `test_pentest.py` y `test_cooks.py`.
5. **Lo sensible, local**: `modelos.personal.yaml` marca `private` a seguridad, investigación, memoria y operaciones; la pasarela salta cualquier proveedor que no sea local para un pedido privado, y el orquestador pide `private=True` si alguna brigada del reparto es privada. Sin modelo local cae a reglas y avisa.
6. **Manifiestos**: 12 brigadas con `manifest.yaml`, `health` y los dos manifiestos (raíz y paquete) idénticos. Sin `__pycache__` ni `egg-info` versionados.
7. **Secretos**: búsqueda de patrones (OpenRouter, NVIDIA, AWS, Meta, GitHub, Mercado Pago) sin coincidencias en archivos versionados; solo `*.plantilla`.
8. **Contenido** no gasta sin aprobación (generación con ComfyUI local; `activar_campana` con `spend`). **Antimalware** manda a VirusTotal solo el SHA-256 y solo de lo que dio positivo local.
9. **PR 28 (modo mixto)** resuelve el riesgo que marqué el 25 nov: aprobar, rechazar, resolver, hablar con la Secretaria, cambiar estado de pedido y cambiar claves piden clave aunque se entre sin clave desde la PC. Los endpoints que quedan con sesión local son de lectura (más `notices/seen`).

### A corregir antes de mergear
**A1. La confianza progresiva puede dejar en automático acciones que mandan mensajes o cobran, y rompe la regla "publicar, pagar, mandar mensajes o borrar siempre piden aprobación".** `RISKY_TAGS` es solo `spend` e `irreversible` (`manifest.py:51`), y las instalaciones personal y de la clienta traen `trust: enabled: true, approvals_to_step_down: 10`. Tras 10 aprobaciones seguidas sin cambios bajan solas a `automatico`, entre otras: `enviar_link_pago` y `confirmar_turno` (Empresas, tag solo `external`: mandan un mensaje y un link de cobro al cliente), `pentest_corrida` (Seguridad), `subir_campana_pausada` (Contenido) y `ejecutar_comando` y `abrir_app` (Operaciones, sin tags). Dos salidas: (a) marcar esas acciones con `irreversible` o `spend`, o (b) que `external` también cuente como riesgoso en `RISKY_TAGS` (cambia el harness: lo decide Damián). Falta un test que recorra todos los manifiestos y verifique que ninguna acción `external`, de borrado o de ejecución baje a automático; hoy solo Trading lo prueba.
**A2. Trading no tiene `.env.plantilla`**, aunque el LIENZO (§7) e `ibkr.py` mandan a buscar ahí `IBKR_HOST`, `IBKR_PORT`, `IBKR_CLIENT_ID`, `IBKR_ACCOUNT` y `TRADING_ALLOW_LIVE`. Es la única brigada sin plantilla (las otras 12 la tienen). Los tests de Trading mencionan además un adaptador OANDA cuyas variables tampoco están en ninguna plantilla. Pendiente para Trading.

### Avisos (no bloquean)
1. `mando` y `voz` van primero a la nube (NVIDIA) en `modelos.personal.yaml`. Quedan protegidos solo cuando el reparto incluye una brigada privada; un pedido que no toque brigadas privadas (o que el clasificador no reconozca) sale a la nube con el texto de Damián. Es lo decidido ("el resto en la nube"); conviene saberlo.
2. `enviar_recordatorio` y `avisar_estado` (Empresas) mandan mensajes a clientes en `automatico`. Ya estaban así antes de esta tanda y son parte del diseño de la brigada, pero contradicen la regla escrita. Decisión de Damián: aclarar la regla (avisos transaccionales automáticos) o pasarlos a `aprobacion`.
3. `LOOPBACK` en `models/config.py` sigue incluyendo `0.0.0.0` (informe del 24 nov).
4. `poner_en_cuarentena` (Antimalware) es automático y mueve archivos; es reversible con `restaurar_de_cuarentena`, lo dejo como OK.
5. Sigue sin probarse con servicios reales: Meta, Mercado Pago, IBKR, OpenRouter, Ollama o LM Studio, VPS, app en teléfono y Windows. Los 1872 tests usan adaptadores simulados, como se pidió.
6. Para el coordinador: ESTADO.md debe decir 1872; mergear el 28 después del 27 (ambos tocan `app.py`, aunque se fusionan sin conflicto).

### Resumen de cierre
- Revisé el PR 27 (integración de las 16 piezas) y el PR 28 contra la lista de 9 puntos; puerta EN VERDE con 1872 tests y ruff limpio.
- Se cumplen las reglas duras de Trading, pentest solo en la PC, lo sensible en local, manifiestos, secretos, y la puerta y el test de imports ya cubren todas las brigadas.
- Dos correcciones antes de mergear: la confianza progresiva puede automatizar acciones `external` (mensajes, link de cobro, pentest) y falta `.env.plantilla` en Trading.
- No se tocó código ni archivos compartidos; solo este informe.
