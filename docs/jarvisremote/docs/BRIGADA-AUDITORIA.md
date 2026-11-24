# 🍳 La Brigada de Auditoría — diseño concreto

> Diseño técnico de la brigada **específica de auditoría**: las estaciones que
> convierten "apuntá a un repo" en "reporte de cliente confiable". No duplica el
> manual general ([`LA-BRIGADA.md`](LA-BRIGADA.md), la metáfora completa) ni el
> blueprint de orquestación — lo aterriza al pipeline de auditoría, que es el
> producto que se vende.
>
> Creado: 2026-09-06. **Por qué existe ahora:** la calibración (ver
> `C:\Users\dam\Downloads\audit-targets\CALIBRACION.md`) expuso con evidencia real
> qué estación falta y por dónde arrancar. Este doc es el plano de construcción.

---

## 1. La idea en una frase

Un reporte de auditoría no lo hace un agente gigante que "sabe todo". Lo hace una
**línea de estaciones**, cada una con una tarea puntual y un contexto chico, que se
pasan el plato en orden. Igual que una cocina: nadie hace el plato entero solo.

**Regla de oro (del manual):** cada puesto se gana su lugar solo si tiene trabajo
puntual Y contexto propio y acotado. No se construye una estación "por si acaso".

---

## 2. Las estaciones del pipeline de auditoría

En orden de recorrido del plato. Cada una dice: qué hace, qué entra/sale, si usa
LLM, y en qué código vive hoy.

### E1 · Reconocimiento (los escáneres) — *ya existe*
- **Qué:** corre Semgrep, Bandit, Trivy, cppcheck/clang-tidy, Ruff, mypy sobre el
  repo. Junta los hallazgos crudos.
- **LLM:** NO (determinista, Tier 0). Acá la calidad la da la **cobertura**, no el modelo.
- **Vive en:** `security_scan_project` / módulos `security/`, `quality/`.
- **Entra:** ruta del repo. **Sale:** lista de hallazgos crudos (con archivo:línea:regla).

### E2 · Contexto por ruta (nuevo, chico) — *falta*
- **Qué:** antes del triage, etiqueta cada hallazgo por DÓNDE está: `app/` (producción)
  vs `tests/`, `examples/`, `docs/`, `migrations/`. Baja la prioridad (o marca como
  "no-cliente") lo que está en código no-productivo.
- **Por qué:** en la calibración, casi todos los "altos" de flask-oficial eran
  `debug=True` en `tests/` y XSS en `examples/`. Un cliente real también tiene `tests/`.
- **LLM:** NO (regla determinista por path). Tier 0.

### E3 · Triage — *ya existe, a reforzar*
- **Qué:** el LLM lee el CÓDIGO REAL de cada hallazgo y decide real / falso positivo,
  con su razón.
- **LLM:** SÍ, y **acá importa el cerebro** (modelo de razonamiento — ver §4). Tier 2.
- **Vive en:** `security/triage.py` (`triage_findings`).
- **Refuerzo pendiente:** que reciba la etiqueta de E2 (no gastar triage en ruido de tests).

### E4 · Config checker (nuevo, QW-4) — *falta*
- **Qué:** chequeo determinista de configuración del framework: `DEBUG=True`,
  `ALLOWED_HOSTS=['*']`, `SECRET_KEY` hardcodeada, `.env`/DB commiteados.
- **Por qué:** los escáneres no miran config; en studybud se escaparon riesgos reales.
  Sube COBERTURA (no precisión).
- **LLM:** NO / Tier 1 opcional. Determinista.

### E5 · Redacción (la narrativa) — *ya existe, a reforzar*
- **Qué:** escribe el resumen ejecutivo + riesgos prioritarios en criollo (qué es /
  por qué importa / cómo se arregla).
- **LLM:** SÍ. Tier 2.
- **Vive en:** `audit_report.py` (`generate_client_report`, `_client_narrative`).

### E6 · Catador / QA (nuevo, QW-3) — *falta — LA PRIORIDAD*
- **Qué:** verifica cada afirmación del reporte contra el código real. Obliga a que
  cada frase **cite y transcriba** el `archivo:línea` del que sale. Si una afirmación
  no se ancla al código real, la rechaza o la corrige.
- **Por qué:** en flask-oficial la narrativa dijo "sesiones con **MD5**" cuando el
  código dice `hashlib.sha1`, y "**RCE en producción**" cuando el `debug=True` estaba
  en tests. El Catador que obliga a citar la línea **hace imposible** esos dos errores.
- **LLM:** SÍ (verificación). Tier 2.
- **Es la estación que convierte "la IA redacta" en "la IA redacta y se verifica sola".**

### E7 · Pase / Agregador — *parcial*
- **Qué:** ensambla el reporte final (ejecutivo + riesgos + anexo técnico + descartados
  por triage) y lo guarda como nota en Obsidian.
- **LLM:** NO (ensamblado determinista). Tier 0.

### E8 · Sous-chef / Orquestador — *parcial (post-venta el formal)*
- **Qué:** coordina las estaciones en **orden topológico** (E1→E2→E3→E4→E5→E6→E7),
  verifica cada devolución, arma el plato. Hub-and-spoke: las estaciones no se hablan
  entre sí, hablan con el sous-chef o dejan su nota en la pizarra (el vault).
- **Hoy:** `audit_report.py` ya orquesta la secuencia de forma lineal. El orquestador
  formal (DAG explícito) recién se justifica cuando haya varias estaciones nuevas.

---

## 3. El flujo (DAG)

```
E1 Reconocimiento ─► E2 Contexto ─► E3 Triage ─┐
                                                ├─► E5 Redacción ─► E6 Catador/QA ─► E7 Pase ─► Obsidian
              E4 Config checker ───────────────┘
                         (todo coordinado por E8 Sous-chef, en orden topológico)
```

Determinista abajo (E1, E2, E4, E7), razonamiento del LLM arriba (E3, E5, E6). Es la
arquitectura que la investigación marca como la mejor: **LLM razonando sobre una base
determinista de SAST.**

---

## 4. Ruteo de modelos por estación (F1-6)

El modelo se asigna por ROL (fijo por estación), no por un juez dinámico:
- **Tier 0 (sin modelo):** E1 Reconocimiento, E2 Contexto, E4 Config, E7 Pase.
- **Tier 2 (razonamiento fuerte):** E3 Triage, E5 Redacción, E6 Catador.
- **El cerebro de Tier 2** conviene que sea un modelo de razonamiento (DeepSeek R1 /
  frontier — decidir con el A/B sobre el caso flask-oficial). Es donde el modelo mueve
  la calidad y donde nació el error del "MD5".
- Para código de CLIENTE: preferir open-weight local en Tier 2 (confidencialidad).

---

## 5. Paralelismo para codebases gigantes (post-venta)

Cuando un repo sea enorme: **git worktrees** — el orquestador reparte el repo en
pedazos, cada uno auditado por una copia aislada de la brigada (sin pisarse), y después
integra los hallazgos. Es la respuesta técnica a "auditar un código gigante". No hace
falta hasta tener clientes con repos grandes.

Comunicación entre agentes: por ahora, hub-and-spoke (todo por el sous-chef) + el vault
como pizarra. El protocolo **A2A** (bidireccional) recién cuando la brigada crezca.

---

## 6. Orden de construcción — de abajo hacia arriba, cada estación ganándose el lugar

No se construye el esqueleto completo (DAG + worktrees + A2A) de una. Se construye la
estación que se paga sola, guiados por la evidencia de la calibración:

1. **E6 Catador / QA (QW-3) — PRIMERO.** Arregla el bug probado (MD5, RCE-en-tests) y
   mejora directo el reporte que se vende. *Pre-venta.*
2. **E2 Contexto por ruta + E4 Config (QW-4).** Precisión (no gritar por código de test)
   y cobertura (mirar la config). *Pre-venta.*
3. **E8 Orquestador formal (DAG) + E5/E3 con ruteo por tier.** Recién cuando haya 2-3
   estaciones nuevas que coordinar. *Post primera venta.*
4. **Paralelismo (worktrees) + A2A.** Cuando aparezcan repos gigantes o la brigada
   crezca. *Post-venta, por necesidad real.*

> Nota de prioridad: los puntos 1 y 2 son **pre-venta** porque arreglan la credibilidad
> del reporte (el producto). Del 3 en adelante es Fase 1, post primera venta. La brigada
> no se construye para tenerla; se construye estación por estación cuando cada una gana
> su lugar.

---

## Referencias
- [`LA-BRIGADA.md`](LA-BRIGADA.md) — el manual general (la metáfora completa de la cocina).
- [`ROADMAP-MEJORAS-RAPHAEL.md`](ROADMAP-MEJORAS-RAPHAEL.md) — QW-3, QW-4, F1-2, F1-6.
- `C:\Users\dam\Downloads\audit-targets\CALIBRACION.md` — la evidencia que justifica el
  orden de construcción (por qué el Catador va primero).
