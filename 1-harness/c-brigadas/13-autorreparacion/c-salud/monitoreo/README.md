# Autorreparación · monitoreo
- **Healthcheck** (`raphael_selfrepair.health:check`, al montar y cada 5 min): da MAL solo con config inválida. Los faltantes son avisos en el detalle: sin raíz (`RAPHAEL_REPAIR_ROOT`), raíz que no existe, raíz que no es repo git, sin `verify_command`, sin modelo. Qué hacer: cargar lo que diga el aviso (ver `b-codigo/autorreparacionautorreparacion.env.plantilla`).
- **Qué mirar en el panel:** pendientes `aplicar_arreglo` / `revertir_arreglo` (esperan tu OK), propuestas por estado (`propuestas`), hallazgos nuevos (`hallazgos`).
- **Eventos:** `arreglo.aplicado`, `arreglo.revertido`, `autodiagnostico.hallazgo`. Alerta sugerida al orquestador: cualquier `arreglo.*` y todo hallazgo nuevo.
- **Auditoría:** `propuesta_creada`, `arreglo_pedido`, `aprobado`, `arreglo_aplicado`, `arreglo_deshecho_por_verificacion`, `arreglo_revertido`, `hallazgos_nuevos`.
