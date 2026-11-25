# Registro · 16-legales · Legales

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 2026-11-25 · Construcción de la brigada (pieza 16)
**Resumen de cierre**
- Se construyó la brigada desde cero (no había código previo): manifiesto con 7 acciones (5 automáticas internas, `emitir_documento` y `borrar_registro` con aprobación e irreversibles), 4 cocineros, health y config. Ninguna acción firma, envía ni presenta.
- Enchufable: fuentes normativas con adaptador real (HTTPS público, sin clave), simulado y apagado; modelo del harness opcional (segunda lectura de riesgos, carta); datos del negocio por config o `LEGALES_NEGOCIO_*` (`b-codigo/legales.env.plantilla`).
- 54 tests en verde (contrato personal y cloud, sin imports ajenos, acciones declaradas), ruff limpio. URLs oficiales de Ley 25.326, Ley 24.240, ARCA facturación y WhatsApp/Meta halladas por búsqueda el 25 nov; no se pudieron abrir desde el contenedor (red bloqueada), así que el modo real queda sin probar.
- Decisión: las plantillas no citan artículos ni plazos sin verificar; ponen `[VERIFICAR: ...]` y `emitir` se niega mientras queden `[COMPLETAR]` o `[VERIFICAR]`. Un texto final lo pasa quien aprueba (`changes.text`).
- Pendiente para el coordinador: sumar la suite `legales` (`16-legales/c-salud/pruebas`) a `gate.py`, la sección Legales a `LIENZO-DAMIAN.md` y la línea a `ESTADO.md`/`CONTEXT.md` (texto en el mensaje del hilo).
- Pendiente para Empresas (15) y Contenido (14): publicar `revision.pedida` antes de mandar o publicar un texto, y `consentimiento.recibido` / `baja.solicitada` al recibir un opt-in o una baja; Legales ya los consume.
- Pendiente para Damián: revisar las plantillas con un abogado antes de entregarlas a una clienta.

## 2026-11-25 · hilo "Dar jefe a las 9 brigadas restantes"
**Resumen de cierre.** Legales ahora tiene jefe con tres efímeros (Documentos, Cumplimiento, Riesgos), así que el orquestador le puede derivar pedidos. Doce tools nuevas (`legales_*`, registradas en `validate`) que reusan el `execute` y el `command` de los cocineros: mismas validaciones, mismo aviso legal. Armar borrador, revisar texto, verificar norma y anotar una baja son automáticos como sus acciones; `legales_emitir_documento` pide aprobación por uso (irreversible). Registrar un consentimiento y borrar un registro NO son tools. Límite: una tool no puede publicar eventos, así que cuando el trabajo pasa por el jefe no salen `documento.borrador_creado`, `revision.lista` ni `riesgo.detectado` (pendiente para Harness: `publish` en el contexto de setup). No son privados (plantillas y textos pensados para salir). 60 tests, ruff limpio.
