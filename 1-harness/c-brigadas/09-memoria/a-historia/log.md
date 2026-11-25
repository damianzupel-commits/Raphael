# Registro · 09-memoria · Memoria · Cerebro

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 2026-11-25 · Hilo "Construir pieza 09 Memoria"
**Resumen de cierre**
- Se portó la brigada al harness v2: 4 cocineros (recuperador, consolidador, asociativo, proactivo), 7 acciones con nivel, 21 comandos, health y suite de contrato en verde (personal y cloud). 149 tests sin red, ruff limpio.
- Enchufable: embeddings real (LM Studio/Ollama, solo en la PC) y simulado; modelo de síntesis por pedido privado. Sin modelo o sin embeddings cae a reglas/palabra clave y avisa; sin modelo local no escribe síntesis.
- Cambios sobre JarvisRemote: estado en el espacio de la brigada (no JSON globales); `recall_query` ya no trae episodios sin el tema; el recuperador cae a palabra clave si la asociativa no trae nada; el registro episódico usa SHA-256 encadenado, sin firma Ed25519 (no hay clave ni win32crypt en la nube); ingesta web (`web_ingest.py`) NO se portó: es de Ingesta.
- Decidido: el vault de Ingesta (`RAPHAEL_VAULT_DIR`) es también el de Memoria por defecto; `nota.ingerida` solo indexa si ya cayó en el vault.
- Pendiente para orquestador: publicar `memoria.turno` al cerrar cada turno. Pendiente para el coordinador: `private: [memoria]` en modelos.yaml (hoy dice `memoria-cerebro`), LIENZO y gate. No verificado: LM Studio/Ollama reales, ni slug del modelo local.

## 2026-11-25 · hilo "Dar jefe a las 9 brigadas restantes"
**Resumen de cierre.** Memoria ahora tiene jefe con tres efímeros (Recuperador, Asociativo, Archivista), así que el orquestador le puede derivar pedidos. Quince tools nuevas (`memoria_*`, registradas en `validate`): doce de lectura, `memoria_guardar` (aditivo, siempre firmada `jarvis`, igual que la acción `guardar_nota`), y `memoria_olvidar` y `memoria_exportar` con aprobación por uso (olvidar es irreversible). Reusan `actions.run` de los cocineros: mismas validaciones y topes. Consolidar y destilar episodios siguen siendo de sus cocineros porque usan el modelo local del contexto. Jefe y efímeros PRIVADOS (solo modelos locales; sin modelo local el reporte sale degradado). 157 tests, ruff limpio.
