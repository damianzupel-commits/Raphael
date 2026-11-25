# Entrega · b-codigo
- `servidor/`: la API (`servidor/api/`, FastAPI, canal de Meta en modo mock por defecto, 33 tests).
- `android/`: la app nativa (Kotlin y Compose, 1.1.0). Se compila con `-Pservidor=https://<dominio>`. La clave de firma va fuera de git.
- `panel-escritorio/`: el panel de Raphael personal. Su código hoy está en `1-harness/b-codigo/panel/`.
