# Ablación del SYSTEM_PROMPT (optimización 2026-09-28)

> Aplicación a Raphael de las ideas del video "Borra todos tus skills" (Boris
> Cherny borró el 80% del system prompt de Claude Code). Objetivo: reducir el
> "hobbling" (instrucciones de más que traban a un modelo capaz) SIN tocar ningún
> gate de seguridad. Rama: `opt/system-prompt-ablacion`. NO se mergea sin A/B.

## Números
| | chars | palabras |
|---|---|---|
| SYSTEM_PROMPT (full, el de siempre) | 22.380 | ~3.514 |
| SYSTEM_PROMPT_SLIM (nuevo) | 4.803 | ~708 |

**~80% menos** — el mismo orden de recorte que hizo Anthropic. Nada se borró
"por fe": ver la clasificación 3R abajo.

## Cómo se activa (A/B, sin romper nada)
`backend/.env` → `SYSTEM_PROMPT_VARIANT=full` (default, comportamiento idéntico al
anterior) o `=slim` (versión adelgazada). La selección vive en
`agent.py::_default_system_prompt()`. El SLIM solo aplica al perfil default y solo
como **fallback** (cuando el mensaje no matchea ningún skill); cuando matchea un
skill, el modelo ya recibe `CORE_PROMPT` + el `prompt_fragment` del skill, que no
cambian.

## Clasificación 3R (qué se hizo con cada parte)
**Requisito → SE CONSERVA (como regla concisa, no párrafo):**
- Frontera de fuente de instrucciones (contenido de tools = dato, no orden).
- Scope no negociable de red (nmap/phone_nmap/sqlmap/zap): solo privado/loopback/
  Tailscale; rechazo de IP pública/terceros; solo Damian edita authorized_targets.
- Gate obsidian-antes-de-fs_write_file (enforced por código).
- fs_write_file sobre backend/ bloqueado; selfrepair dry-run + proposal_id de Damian.
- cloud_expert con confirm_non_sensitive; nunca código de cliente a la nube.
- Código de cliente: nunca nube/repo público/mezcla; fuente de verdad = _REGLAS.md.
- security_audit_find_fix_verify + requested_rule_id; "auditado" ≠ "verificado".
- Fixes de bugs reales: venv + `-m pip`/`-m pytest` (nunca global), leer exit_code.

**Ruido → SE CORTA:**
- La re-descripción exhaustiva de cada tool (ya se autodescriben en su schema:
  el bloque largo de capacidades de PC/celular/cámara/etc.).
- La narración paso-a-paso que un modelo capaz no necesita (los "primero X,
  después Y, después Z" que no son gates).
- Explicaciones duplicadas del detalle de dominio (auditoría/pentest/worker
  selection) que YA viven en los `prompt_fragments` de skills.py — el SLIM es el
  fallback, no repite lo que el skill ya inyecta.

**Receta → SE CONVIERTE a tarea + guardrails + criterio de término:**
- "Ejecutá lo que haga falta; terminaste cuando está hecho y verificado, no cuando
  lo anunciaste" en vez de secuencias rígidas de pasos.

## Cómo medir (no mergear sin esto)
1. Correr la suite: `cd backend && pytest` con `SYSTEM_PROMPT_VARIANT=full` y con
   `=slim` — no debería haber diferencia en los tests (no dependen del prompt), es
   solo el control de que nada se rompe estructuralmente.
2. A/B real de calidad: elegir 5-8 tareas representativas (una auditoría, un fix de
   seguridad, crear un proyecto Python, un escaneo de red rechazado por scope, una
   tarea de PC, una de celular) y correrlas con cada variante. Comparar: ¿respeta
   los gates igual? ¿resuelve igual de bien con menos andamiaje?
3. Si el SLIM mantiene calidad → adoptarlo. Si baja en algún caso → ver qué regla
   faltó y devolverla (ablación línea por línea, como en el video).

## ⚠️ La trampa que el video ignora: depende del modelo
El prompt óptimo NO es universal. Un modelo fuerte (DeepSeek cloud, Opus-class)
aguanta el SLIM. Un modelo local chico (jarvis-text-lite, 8B) puede necesitar más
andamiaje y rendir mejor con el FULL. Por eso esto es un FLAG, no un reemplazo:
- Con cerebro cloud → probar `slim`.
- Con local chico → quizás quedarse en `full`.
- A futuro: se puede atar la variante al tier de modelo automáticamente.

## Fase 2 — fragmentos de skills (2026-09-28)
Mismo tratamiento a los `prompt_fragment` de skills.py (también 100% model-facing).
Mecanismo: campo `Skill.prompt_fragment_slim` + flag `SKILLS_PROMPT_VARIANT=full|slim`
(default full). `prompt_for_active_skills` usa el slim solo si el skill lo tiene
definido; si no, cae al full sin romper. Se puede combinar con SYSTEM_PROMPT_VARIANT.

Hechos CORE_PROMPT (se carga en CADA turno con skill) + los 6 fragmentos con
contenido real. Los livianos (phone_control, desktop_control, memoria,
datos_externos) se dejaron como están (ya son concisos o recién escritos).
| bloque | full (palabras) | slim | recorte |
|---|---|---|---|
| CORE_PROMPT | 472 | 157 | −67% |
| investigation | 681 | 209 | −69% |
| security_audit | 574 | 184 | −68% |
| pentesting | 520 | 205 | −61% |
| malware_protection | 335 | 139 | −59% |
| code_delegation | 288 | 91 | −68% |
| web_forms | 401 | 165 | −59% |
| **TOTAL (core+6)** | **3.271** | **1.150** | **−65%** |

Gates conservados en cada uno: scope de red no negociable + legal (pentest);
propose-only + confirmación de Damian + rol acotado (investigation);
find_fix_verify + requested_rule_id + self-code + venv/pytest (security_audit);
cuarentena reversible + confirm de borrado + integridad (malware); cloud_expert
con confirmación + nunca cliente a la nube (code_delegation); gate de submit con
preview_token + inyección de página ignorada (web_forms); obsidian-gate (core).
Cortado: la narración por-tool (cada tool se autodescribe en su schema).

## Ritual de poda ("cada 6 meses")
Re-correr esta ablación cada vez que se cambie de modelo o salga uno nuevo, y
engancharlo con la consolidación de la memoria episódica
(`docs/SPEC-memoria-episodica.md`).
