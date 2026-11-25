# Autorreparación · b-codigo
El código de la brigada para el harness v2, portado de `3-mando/c-referencia/self-repair/` (JarvisRemote). Brigada `autorreparacion` 2.0.0, solo edición **personal** (corre en la PC de Damián; en la nube no monta).

## Qué hay
- `manifest.yaml` (y su copia dentro del paquete, `scripts/sync_manifest.py`): tres cocineros, dos acciones, comandos, eventos y config.
- `src/raphael_selfrepair/`
  - `cooks/propose.py` **proponer**: guarda propuestas `old_snippet -> new_snippet` en seco (diff y razón), con id `sf-xxxxxxxx`. `redactar` le pide el par de snippets a la IA; sin modelo avisa y no inventa.
  - `cooks/apply.py` **aplicar**: `aplicar` / `revertir` piden la acción `aplicar_arreglo` / `revertir_arreglo` (**nivel `aprobacion`, etiqueta `irreversible`**); recién con tu OK escribe.
  - `cooks/introspect.py` **introspección**: `analizar` busca patrones de falla en el registro de tool calls, `reflexionar`/`reflexiones` guardan criterio, `autoconocimiento` dice qué es y qué no.
  - `guardrail.py` líneas rojas (ruta pura, sin modelo); `fixer.py` reemplazo mecánico, diff, commit propio, verificación; `analyzer.py` patrones; `health.py` salud.
- `autorreparacionautorreparacion.env.plantilla`: lo que tenés que completar (ver también `3-mando/a-conocimiento/LIENZO-DAMIAN.md`).

## Cómo se protege (todo en código, con tests)
1. **Nada se escribe sin tu aprobación**, por propuesta. La acción lleva solo el id y una huella (sha256 de archivo+snippets): los snippets salen de la propuesta guardada, no de lo que llegue con la aprobación.
2. **Líneas rojas** (al proponer Y al aplicar): alcance del pentest, secretos, auth, políticas/aprobaciones/auditoría/aislamiento del harness, manifiestos y niveles de autonomía, `installation.yaml`, `modelos.yaml`, la puerta (`gate.py`), `.git/`, `.github/` y esta misma brigada. Se chequea la ruta dada y la ya resuelta (`..`, symlinks). La config puede sumar fragmentos, nunca sacar.
3. **El snippet tiene que aparecer una sola vez** y seguir apareciendo al aprobar (si el archivo cambió, no aplica).
4. **Verificación y vuelta atrás:** con `verify_command`, si falla tras aplicar se deshace solo. `revertir` (también con aprobación) hace el reemplazo inverso.
5. **Git:** si la raíz es un repo, cada arreglo va en su propio commit con `git add -- <archivo>` (nunca `-A`).
6. **Solo texto UTF-8 de hasta 2 MB**; conserva CRLF; escritura atómica.
7. Si bajás `aplicar_arreglo` a `automatico` en `installation.yaml` el harness lo permite (no tiene pisos): **no lo hagas**; la confianza progresiva sí está bloqueada para `irreversible`.

## Config (`installation.yaml > brigades > autorreparacion > config`)
```yaml
autorreparacion:
  active: true
  config:
    root: "D:\\Raphael Ultimate\\raphael"      # o RAPHAEL_REPAIR_ROOT
    verify_command: ["python", "-m", "pytest", "-q"]
    git_commit: true
    ai_private: false          # true = solo modelo local para redactar
    audit_log_path: ""         # JSONL de tool calls para la introspección
    analyze_every_minutes: 0
    extra_protected: []
```
Formato de cada línea del registro de tool calls: ver el docstring de `analyzer.py`.

## Probar
`cd ../c-salud/pruebas && python -m pytest -q` (sin red, sin claves) · `ruff check` desde `1-harness`.
