# Memoria · Cerebro · mantenimiento
Tareas que se corren de vez en cuando para que la brigada siga sana: regresiones, migraciones de datos, limpieza y actualizaciones.
Todavía vacío. Cada script nuevo va con una línea acá: qué hace, cuándo correrlo y qué toca.

## Scripts
- `revisar_vault.py <carpeta> [--sensibles a,b] [--excluidas c]`: revisa un vault ANTES de conectarlo al Cerebro. Solo lee (no escribe,
  no borra, no llama a ningún modelo ni muestra contenido): cuenta las notas que va a leer la brigada por carpeta, las que saltea
  (sistema de Obsidian, plantillas, ilegibles), las que pasan el tope de texto a embeber y las carpetas marcadas como sensibles.
  Correrlo cuando se cambia de vault o se sospecha que algo no se lee.
