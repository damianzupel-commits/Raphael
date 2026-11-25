# Registro · 13-autorreparacion · Autorreparación

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 25 nov 2026 · Portada al harness v2 (hilo "Construir pieza 13 Autorreparación")
**Resumen de cierre**
- Se portó la brigada desde `3-mando/c-referencia/self-repair/`: paquete `raphael_selfrepair` con tres cocineros (proponer, aplicar, introspección), `manifest.yaml` (solo edición personal; `aplicar_arreglo` y `revertir_arreglo` en `aprobacion` + `irreversible`), `health` y `setup`. 106 tests en verde, `ruff` limpio, suite de contrato pasando.
- Diseño: la aprobación del harness reemplaza al `proposal_id` literal en el chat; la acción lleva solo id y huella y los snippets salen de la propuesta guardada. Se sumaron verificación con deshacer automático, `revertir`, líneas rojas con `..`/symlinks y commit propio por arreglo. Las líneas rojas de JarvisRemote (`authorized_targets`, auth, secretos, config) se pasaron a la estructura v2 (políticas, aprobaciones, auditoría, manifiestos, `installation.yaml`, `gate.py` y esta brigada).
- Todo lo que falta de Damián quedó enchufable: `RAPHAEL_REPAIR_ROOT`, clave del modelo del rol `cocinero` (NVIDIA en personal, según `modelos.yaml`; solo para `redactar`) y `verify_command`; sin eso la brigada monta, avisa y no inventa. Plantilla en `b-codigo/autorreparacionautorreparacion.env.plantilla`.
- Se decidió: la introspección lee un JSONL de tool calls (formato en `analyzer.py`) o `entries` por comando; no lee la auditoría del harness porque un cocinero no tiene acceso a ella.
- Quedó: probar contra el repo real en la PC de Damián (no se probó en Windows ni con IA real), y lo anotado como pendiente para el coordinador y otras piezas (abajo).

**Pendiente para el coordinador:** sumar la suite `selfrepair` a `gate.py` (carpeta `1-harness/c-brigadas/13-autorreparacion/c-salud/pruebas`), filas en `ESTADO.md` y `LIENZO-DAMIAN.md` (texto listo en la descripción del PR).
**Pendiente para Orquestador/Harness:** exportar el registro de tool calls del agente a JSONL en el formato de `analyzer.py` (hoy no existe en v2) para que la introspección tenga qué leer; y reenviar el evento `arreglo.aplicado` / `autodiagnostico.hallazgo` como aviso proactivo.
- Nota: el pendiente de aprobación muestra el diff truncado a 4.000 caracteres; el completo está en `ver_propuesta`.
