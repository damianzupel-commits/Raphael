# Raphael Empresas · monitoreo
Cómo se sabe si la brigada anda bien mientras corre.
- Healthcheck: la función que declara `health` en `b-codigo/manifest.yaml`. Hoy: `raphael_empresas.health:check` (y `setup`: `raphael_empresas.health:validate`).
- Métricas: qué se mide (latencia, errores, aprobaciones pendientes) y dónde se mira (panel del harness).
- Alertas: qué dispara un aviso al dueño y por qué canal.
Anotá acá cada chequeo nuevo con qué mira y qué hacer si falla.
