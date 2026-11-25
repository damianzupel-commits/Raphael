# Investigación · monitoreo
- Healthcheck: `raphael_investigacion.health:check` (al montar y cada 5 min). Da MAL solo con una config inválida. Que falte proveedor de búsqueda, `INVESTIGACION_LOG_KEY` o `inbox_dir` NO es salud mala: va en el detalle.
- El cocinero `forense` también da mal si el registro encadenado de algún caso fue alterado.
- Qué mirar: temas con `last_status` "sin proveedor", casos con `verificar_log` en falso, pendientes de confirmación viejos.
