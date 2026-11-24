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
