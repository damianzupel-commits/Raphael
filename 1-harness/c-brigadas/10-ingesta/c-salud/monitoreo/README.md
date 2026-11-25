# Ingesta · monitoreo
- **Healthcheck:** `raphael_ingesta.health:check` (al montar y cada 5 min). Da mal solo si la config es inválida o el vault no se puede escribir. Que falte yt-dlp o la carpeta del vault se dice en el detalle pero no es salud mala.
- **Estado a mano:** comando de lectura `estado` (modo de cada fuente, vault, cuántas notas, cola, fallidos y vigiladas), y `cola`, `fallidos`, `vigiladas`, `notas`.
- **Alertas:** el evento `ingesta.fallo` (fuente, ref, motivo) lo puede tomar el orquestador para avisar. Un video sin subtítulos o un 429 agotado generan uno.
- **Qué mirar:** `fallidos` crece = YouTube bloqueó (ver cookies en `ingesta.env.plantilla`) o hay muchos videos sin subtítulos; `cola` que no baja = revisar si la brigada está caída o el nivel de `ingerir_item` quedó en aprobación.
