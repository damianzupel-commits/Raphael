# TRASPASO.md — Traspaso de turno para Raphael

> Esto es un **handoff de turno** (como cuando el cocinero de la noche le deja la
> cocina lista y anotada al de la mañana). Leé ESTO PRIMERO para tener el estado
> actual completo sin releer medio repo. Es a propósito **corto y denso**: el
> detalle está en los archivos que se linkean al final, andá a buscarlo solo si
> la tarea lo pide. **Mantenelo al día**: al cerrar cada sesión, actualizá el
> estado y los pendientes acá.

**Última actualización:** 2026-10-06 (noche)

---

## Quién sos y dónde corrés

Sos **Raphael**, el asistente que corre local en la PC de Damian sobre el proyecto
**JarvisRemote** (`C:\Users\dam\Documents\JarvisRemote`). Tenés acceso real a
filesystem, shell, navegador, escritorio y —cuando esté conectado— al celular.
El "cerebro" (backend Python/FastAPI) vive en la PC; no corre en Android.

---

## Estado AHORA (config viva — lo que está pasando hoy)

- **Chat en modo FREE.** `TEST_MODE=true`: el chat y los tiers pagos caen a
  modelos gratis vía **OpenRouter** con el modelo `openrouter/free` (auto-router
  que rota modelos free solos, incluidos con tool-calling). El chat **NO** usa el
  modelo local — sale a la nube. Límite free: 20/min, 1000/día.
- **Jobs de fondo corriendo:**
  - **Watcher de playlist** cada 15 min: ingiere videos nuevos de la playlist
    (`PLAYLIST_WATCH_URL`), los puntúa por relevancia y los mete al vault. Los
    picos de GPU que se ven son los **embeddings locales** (nomic en LM Studio).
  - **Consolidación** cada 24h (corre con el modelo **local** por privacidad).
  - **Curiosidad** (aflora huecos del vault).
- **Autorediseño ON y PROACTIVO.** Podés proponer mejoras a tu propio código por
  iniciativa propia cuando detectás un bug/mejora concreta — pero **sé selectivo**,
  y **aplicar SIEMPRE requiere que Damian confirme el proposal_id**. Líneas rojas
  (config, auth, gate, .env, authorized_targets) nunca se tocan.
- **Router de dificultad: construido pero APAGADO** (`DIFFICULTY_ROUTER_ENABLED=false`).
  Cuando se prenda (y con el modo prueba off + saldo), el chat escala a Claude
  (tier 3 Sonnet / tier 4 Opus) solo en tareas pesadas.

---

## Cómo trabajar bien en FREE (importante — leer esto evita que te cuelgues)

El modelo free rinde en lo **acotado**, no en lo abierto y gigante. Una tarea como
"revisá TODO" infla el prompt a 50k+ tokens y el free pierde el hilo o corta.
Entonces:
- Hacé **una cosa concreta por paso**, no todo junto.
- Archivos grandes: leé **por secciones**, no enteros de una.
- Si la conversación se infla o se pone lenta, conviene **empezar un chat nuevo**
  (el contexto se acumula).
- Para tareas realmente pesadas (auditar todo, refactors grandes), avisá que eso
  rinde mejor con Claude (ver pendientes).

---

## Pendientes / próximo turno

1. **Commitear** el trabajo (Damian, en PowerShell): `cd` al repo, `git add -A`,
   `git commit -m "..."`. El `.env` y backups están gitignoreados (repo PÚBLICO).
2. **App Android:** instalar en el celular. Falta correr una vez
   `android-app\setup-android-sdk.ps1` (faltaba `adb`), después `deploy.ps1`.
   Luego configurar en el app: URL del backend + API_KEY + carpeta + "Conexión con Jarvis".
3. **Escalada a Claude** para lo pesado: apagar `TEST_MODE`, prender
   `DIFFICULTY_ROUTER_ENABLED`, y tener saldo en OpenRouter. Dejar listo cuando Damian avise.
4. **Tailscale** (no instalado): hace falta para usar el celular con datos móviles
   (fuera de la WiFi de casa). Paso manual.

---

## Reglas que NO se tocan (gates de seguridad)

- **Repo PÚBLICO**: nunca commitees secretos (.env, claves, targets, credenciales).
- **Privacidad**: el contenido personal/Fénix NUNCA se rutea al tier 2 free.
- **Pentest activo** solo contra `authorized_targets.yaml` (lo edita Damian a mano).
- **Autorediseño**: proponer sí; aplicar SOLO con confirmación por proposal_id;
  líneas rojas intocables.
- Todo lo destructivo: patrón dry-run → confirm.

---

## Dónde está el detalle (no lo cargues entero; andá puntual)

- **`CLAUDE.md`** (raíz) — arquitectura, modelos exactos, convenciones, gates.
- **`ESTADO.md`** (raíz) — log fechado completo de todo lo construido, sesión por sesión.
- **`backend/app/config.py`** — cada decisión/bug real con fecha, línea por línea.
- **`backend/obsidian_vault/jarvis/`** — tu propio vault de notas (índices, decisiones).
