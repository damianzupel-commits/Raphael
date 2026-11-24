# Análisis de código de Raphael — de punta a punta

> Hecho el 2026-09-25 midiendo el código real (no de memoria). Ver los 3 mapas
> generados: arquitectura, flujo del agente, y mapa de calor + veredicto
> (`raphael-codigo-1/2/3.png`).

## Los números (medidos)
- **Backend `app/`: ~26.500 líneas**, 19 paquetes.
- **104 tools reales** (`register_tool(`), top: investigation ×18, phone ×12,
  malware ×11, desktop ×10, browser ×7, filesystem ×6.
- **Hotspots:** `agent.py` 1.401 · `tools/` 6.922 · `investigation/` 3.459 ·
  `config.py` 773 · `audit_report.py` 728.
- **Tests: 112 archivos, ~21.600 líneas** (casi 1:1 con el código de la app).
- Solo **3 marcadores TODO/FIXME/HACK** en todo el repo.
- **7 imports perezosos** para esquivar ciclos de import.

## Arquitectura (mapa 1)
Capas limpias, de arriba a abajo:
1. **Interfaces:** tray-app PySide6 (7.7k), Android, celular (WebSocket).
2. **API:** FastAPI (`main.py`) — `/api/chat`, `/ws/phone`, routers (codebase,
   obsidian, investigation, brigada), health.
3. **Núcleo:** `agent.py` — el loop LLM→tool→LLM + guardas de contexto/seguridad +
   persistencia.
4. **Dominios:** auditoría (security+quality+findings), brigada (harness), codebase,
   obsidian, malware, pentest+network, investigation, ingestion, forms, selfrepair,
   testing.
5. **Tools:** 104, la superficie de integración.
6. **Cerebro:** DeepSeek V4 (OpenRouter) o local (Ollama) + embeddings (LM Studio).

## Flujo del agente (mapa 2)
Mensaje → prepara contexto (recorta por presupuesto de tokens) → LLM decide →
¿pide tool? → ejecuta con guardas (audit-log, gates dry-run→confirm, anti-loop) →
agrega resultado → vuelve al LLM → texto final → persiste (y voz lo habla).
Tope: `max_agent_iterations`.

## Veredicto (mapa 3)
**Código sólido y coherente — no está "enredado".** Capas limpias, agente bien
descompuesto en funciones nombradas (no un bloque gigante), guardas de seguridad
reales, y un test-suite enorme.

- **Fortaleza:** arquitectura por encima de la formación formal; testeada y con
  criterio de seguridad.
- **Riesgo 1 — hotspots:** `agent.py` (1.4k) y `tools/` (6.9k) concentran demasiado
  y crecen con cada feature.
- **Riesgo 2 — amplitud:** ~la mitad del código es lab (investigation, malware,
  ingestion, pentest), no producto → mantenimiento que no cobra.
- **Riesgo 3 — 7 imports perezosos:** las fronteras de módulo no están del todo
  limpias (hay acoplamiento que se esquiva a mano).
- **Desperdicio:** ~21.6k líneas de tests que casi no se corren.

**Qué haría (sin reescribir):**
1. Partir `agent.py` en un paquete (`agent/`: loop, contexto, guardas, persistencia).
2. Rutear tools por dominio (QW-1): no cargar las 104 en cada llamada.
3. Correr los tests con ritmo (el activo más subutilizado).

**Contener, no reconstruir.** La base es buena; el peligro es dejar crecer los
hotspots y la amplitud sin freno.
