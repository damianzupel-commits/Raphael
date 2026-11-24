| Componente | Estado | Nota |
|---|---|---|
| Método de brigadas (Etapa 1) | ✅ construido y versionado | Spec declarativo + motor genérico + framework de validación compartido + playbook (`PLAYBOOK-brigadas.md`) |
| **Etapa 2: el orquestador crea brigadas** | ✅ construida y versionada | Borrador + gate firmado (Ed25519/DPAPI); UI (pestaña Brigadas), chat y API. Diseñador **probado con nemotron real** (1 intento, borrador válido). Pendiente: edición de borradores en la UI, versionado de borradores |
| **Modelo de interacción decidido (Ayudantes → Jefe → Orquestador → Usuario)** | ✅ implementado (2026-11-15) · ⏳ sin validación real | Contratos, modelo por rol, jefe con LLM propio (plan, paralelo, síntesis, reporte), voz del orquestador con fidelidad verificable, memoria de conversación, feed y UI. Tests sin red en verde. Falta correr `validation.todas` con modelos y re-fijar el baseline de Cerebro; P6 sin empezar. Ver `docs/ARQUITECTURA-RAPHAEL.md` §0 |
| **Optimizaciones P6 (O-1…O-11)** | ✅ implementadas (2026-11-15) · ⏳ medidas solo con datos inventados | Razonamiento por fase, ruteo por reglas (banco de 61), extractos, latidos, tiempos por fase, respaldo por rol, `ROLES_EN_LOCAL`, versiones de borradores. Instrumentos: `python -m validation.medir` y `python -m validation.calibrar_consolidacion`. Falta: calibrar consolidación con el vault real, Whisper medium/VAD, probar la UI en el navegador |
| **Watchdog del orquestador** | ✅ construido y versionado | Loops / falta de progreso / timeout / errores; corta y avisa en el feed. Sin calibrar con corridas reales de un modelo colgado |
| Brigada Cerebro | ✅ construida · ⚠️ **a re-validar** | PASÓ 4/4 el 2026-11-12 con el flujo anterior (el jefe respondía directo). Desde el 2026-11-15 delega en `cerebro-recuperador` y el mensaje lo produce la voz del orquestador: ese baseline ya no es comparable hasta una corrida verde con `--rebaseline` |
| Brigada Investigación | ✅ construida · ⚠️ INCOMPLETA | Ruteo y Forense PASAN; Scout SIN VALIDAR (falta `BRAVE_SEARCH_API_KEY`); sin baseline hasta que corra Scout |
| Brigada Seguridad | ✅ construida (spec + validación) · ⏳ sin corrida real | La corrida real exige la VM de laboratorio + nmap/ZAP/sqlmap + la IP escrita **a mano** en `authorized_targets.yaml` |
| **Brigada Video** | ✅ construida (spec + tools + validación) · ⏳ sin corrida real | 24 tools `video_*` sobre ffmpeg; probada con videos sintéticos. Falta: ffmpeg instalado en la PC de Damian, probar con videos reales y correr `python -m validation.video`. Ver `BRIGADA-VIDEO.md` |
| Módulo Scout | ✅ funcional y versionado | Búsqueda enchufable Brave + SearXNG; modelo propio (Groq) |
| Orquestador standalone (:8010) | ✅ en git | Crea brigadas, vigila con el watchdog; todo su modelo es nemotron/NVIDIA |
| Monolito (:8000) | ✅ operativo | Chat global ahora en nemotron/NVIDIA (prueba de Damian) |
| Modelo del orquestador | nemotron por **NVIDIA oficial** | `ORQUESTADOR_LLM_*`; la key solo del `.env` |
| Privacidad | ⚠️ asumida a conciencia | Con todo en nemotron, las notas que lee Cerebro y los mensajes salen a NVIDIA; los embeddings siguen locales. Reversible por `.env` |
| **Voz local del orquestador** | ✅ construida y versionada · ⏳ micrófono real sin probar | faster-whisper + Piper es-AR en esta PC (CPU), reusando el stack del prototipo; ida y vuelta real verificada. Falta probar la grabación con micrófono en la ventana app |
| Registro doble (máquina + humano) | ✅ al día | JSON en `backend/validation/results/` (gitignoreado) + rondas 01–09 en `Documents\Validacion-Brigadas\` |
| 8 fases del cerebro | ✅ todas hechas | 2026-10-04/05 |
| Etapa A (cerebro de memoria) | 🔨 casi | Falta atención/gating, separación de patrones, metacognición plena |
| Etapa B (lazo cerrado) | ⚠️ sustrato construido | `feedback.py`; falta el hook automático en el loop del agente |
| Etapas C/D | 📋 decididas, a construir | Curiosidad local primero; grafo auto-tunea, código con OK |
| Jefes → Sonnet (tier 3) | 📋 pendiente | Un solo punto de cambio en `brigades/config.py` cuando haya key |
| Proactivo de Cerebro | ⏸️ OFF | `CEREBRO_PROACTIVE_ENABLED=false` (escribe en el vault) |
| App Android | ⚠️ falta instalar | `setup-android-sdk.ps1` + `deploy.ps1`; luego configurar URL+API_KEY |
| Tailscale | ❌ no instalado | Para usar el celular con datos móviles |
