# Experimento: motor de decisiones "System 1" para Raphael — LAYA (elegido) / Jev (alternativa)

> Plan de experimento. Creado el 2026-09-26. Nace de la charla sobre los "modelos de
> decisión" (System 1): devuelven decisiones **tipadas + confianza calibrada** en vez
> de texto, así que son rápidos, baratos y no pueden alucinar el formato.
> Fundamentos conceptuales en `FUNDAMENTOS-caja-negra-y-verificacion.md`.
>
> **Encuadre:** experimento de **lab (Investigador)**. NO se toca el producto hasta
> pilotear y medir.
>
> **Nota:** el archivo se llama "JEV" por historia; hoy cubre **las dos opciones** y
> la decisión es **LAYA** (ver §2).

---

## 1. El concepto (por qué sirve, sea cual sea)
Varios pasos de la Brigada son **decisiones** (clasificar, puntuar, rutear, verificar),
no escritura. Hoy los hace DeepSeek (LLM): caro, lento, y por eso **capado** (triage
limitado a 30 hallazgos por corrida). Un modelo "System 1" —tipado, calibrado, en
paralelo— podría hacer **todas** esas decisiones, subiendo cobertura y bajando
costo/tiempo, sin perder calidad.

## 2. Las dos opciones y LA DECISIÓN

| | **Jev (TypeSafe)** | **LAYA (Convai)** ← **ELEGIDO** |
|---|---|---|
| Qué es | Modelo de decisiones System 1 | Modelo de decisiones System 1 |
| Acceso | Beta / lista de espera | **Disponible ya (Hugging Face)** |
| Licencia / costo | Propietario, API paga | **Apache 2.0 — gratis, uso comercial** |
| Dónde corre | Nube de TypeSafe | **Local, en la RX 6700 XT** |
| Tamaño | Grande, opaco | **421M — chico, corre en tu PC** |
| Velocidad | 40–200x vs LLM (afirmado) | ~33 ms por decisión |
| Idiomas | — | 100+ |

### Por qué elegimos LAYA (el detalle de la decisión)
1. **Coherencia con la filosofía del proyecto.** Raphael es local-first, gratis y
   accesible. LAYA es open-source y corre en la máquina de Damian; Jev es nube y pago.
   Elegir Jev contradiría el ADN del proyecto.
2. **Disponible YA, sin fricción.** LAYA se baja hoy de Hugging Face. Jev está en
   lista de espera — no podríamos ni empezar el experimento.
3. **Cero costo y cero dependencia de proveedor.** Con LAYA no hay factura ni riesgo
   de que una empresa nueva cambie precios/condiciones o cierre. Es tuyo.
4. **Sin datos afuera.** Las decisiones (código del cliente, hallazgos) se procesan
   local. Para un producto de **seguridad**, mandar código de clientes a la nube de un
   tercero es un problema de confidencialidad; LAYA lo evita.
5. **Encaja con el diferencial de venta.** "Corre 100% local, tus datos no salen de tu
   máquina" es un argumento fuerte para un auditor de seguridad.

### Cuándo reconsideraríamos Jev (alternativa, no descartada)
- Si LAYA (más chico, 421M) **no alcanza la precisión** que necesitás en el triage,
  medido en el experimento (§5).
- Si necesitaras **escala/velocidad** que el hardware local no da.
- En esos casos, Jev queda como plan B (o un tercer modelo de decisión que aparezca).
- Se prueba **con el mismo experimento**, así la decisión es por datos, no por moda.

## 3. La restricción que esto destraba (el porqué del experimento)
- Hoy: `_MAX_AUTO_TRIAGE = 30` en `audit_report.py` — solo 30 hallazgos pasan por
  triage LLM. En la auto-auditoría hubo **2598 crudos**; el resto quedó sin filtrar.
- Con un modelo de decisión local: triagear los **2598** en paralelo, gratis. De
  "revisé una muestra" a "revisé todo". **Ese salto de cobertura es el valor #1.**

## 4. Arquitectura objetivo: dos pisos (cheap-filters / expensive-decides)
1. **LAYA decide sobre TODO** (rápido, local, gratis) + confianza.
2. Lo que quede **con confianza baja** se **escala a DeepSeek** (el que razona) o al
   humano.
3. Cubrís el 100% pagando el LLM solo por el ~5% difícil.

## 5. Dónde enchufarlo — la Brigada (orden de prueba)
1. **E3 Triage** *(piloto)* — `[real, falso_positivo]` + confianza por hallazgo.
2. **Severidad** — escala `[crítico, alto, medio, bajo]`.
3. **Routing de tools (QW-1)** — clasificar la tarea → qué dominio/tools cargar.
4. **Checks del Catador (E6)** — `¿el código respalda esta afirmación? [sí, no]` +
   confianza, en paralelo por afirmación.

## 5·B. Dónde más enchufar — el vault y los grafos (la memoria de Raphael)
Raphael tiene **tres estructuras de recuperación**, no una: embeddings (búsqueda
semántica del vault), el **grafo de wikilinks** del vault, y el **grafo de código**
(tree-sitter: archivos/funciones/clases con imports como aristas). LAYA **no
reemplaza** ninguna —no es modelo de embeddings ni construye/guarda el grafo, y no
redacta notas— pero es la **función de decisión** que hace que esas estructuras
encuentren mejor, barato y local. Distinción clave: embeddings traen lo *parecido*,
el grafo trae lo *conectado*, y **LAYA decide** en ambos recorridos.

### B.1 — Re-ranking / filtro de relevancia del vault *(el más visible; buen 2º piloto)*
- Hoy: los embeddings devuelven notas "parecidas" a la consulta, pero *parecido ≠
  responde*. Entra ruido.
- Con LAYA: por cada nota candidata → `¿responde a lo que se preguntó? [sí, no]` +
  confianza. Local, en paralelo, gratis. Mismo patrón de **dos pisos**: el barato
  filtra, el LLM solo interviene en lo dudoso.
- **Valor:** sube la precisión de la memoria sin gastar LLM. Más visible que el
  triage (se nota al toque en las respuestas).

### B.2 — Auto-clasificar, taggear y sugerir links *(ordena el vault solo)*
- Al crear/guardar una nota: `¿a qué vault va? [seguridad, investigación]`,
  `¿qué tema?`, `¿es duplicada de una existente? [sí, no]` + confianza.
- **Links faltantes:** para pares de notas cercanas, `¿deberían estar conectadas?
  [sí, no]` + confianza → Raphael propone los wikilinks que faltan y el grafo del
  vault se densifica solo.
- **Valor:** clasificación y curaduría que hoy pagarías al LLM, hechas locales y en masa.

### B.3 — Guiar el recorrido del grafo (GraphRAG con timón) *(lo más ambicioso)*
- Problema del recorrido: expandir *todos* los vecinos de un nodo es caro y trae ruido.
- Con LAYA, **en cada salto**: `¿vale la pena seguir por este nodo? [sí, no]` +
  confianza. El paseo por el grafo pasa de ciego a **dirigido**, barato y local.
- Aplica a los dos grafos: el de wikilinks (memoria) y el de código.

### B.4 — Podar el grafo de código para el Auditor *(alimenta a E5/E6)*
- En cada arista (un import, una llamada): `¿esta relación es relevante para este
  hallazgo? [sí, no]`.
- **Valor:** al modelo que redacta (DeepSeek) le pasás **solo el subgrafo que importa**,
  no el árbol entero. Menos ruido, mejor contexto, menos tokens.

> **Disciplina (igual que en la Brigada):** en todos estos casos LAYA **decide**,
> nunca escribe ni indexa. La calibración se valida sobre datos tuyos antes de
> confiar en los umbrales, y lo dudoso escala al LLM o al humano (§4, §7).

## 6. Qué medir (sobre un set etiquetado — usar `Auditorias/EJEMPLOS/`)
- **Precisión/recall vs DeepSeek** en triage.
- **Velocidad** por decisión y por corrida.
- **Costo** (LAYA ≈ 0; comparás contra lo que gastás con DeepSeek).
- **Cobertura** (debería ser TODOS los hallazgos).
- **Calibración:** cuando LAYA dice "90% seguro", ¿acierta ~90%? (Decide el umbral de
  escalado.)

## 7. Umbrales a calibrar (con TUS datos)
- **Auto-decisión:** confianza ≥ 0.9 → se acepta la decisión de LAYA.
- **Escalado:** confianza < 0.9 → va a DeepSeek/humano.
- Ajustar midiendo sobre tu set etiquetado, no adivinando.

## 8. Plan por fases
- **Fase 0:** bajar LAYA de Hugging Face y hacerlo correr local (test de humo).
- **Fase 1 (lab, shadow mode):** LAYA corre en paralelo al DeepSeek en E3, **sin
  decidir nada** — solo se comparan resultados.
- **Fase 2:** si LAYA iguala a DeepSeek en el set etiquetado → activarlo como primer
  piso (con escalado por confianza baja).
- **Fase 3:** extender a severidad, routing y Catador.

## 9. Disciplina / caveats
- **Solo decisiones, nunca escritura:** E5 (redacción) y el informe siguen en DeepSeek.
- **"No alucina el formato" ≠ "siempre acierta":** puede elegir mal una opción válida;
  la confianza calibrada + el escalado es lo que lo cubre.
- **Validar la calibración en tu data** antes de confiar en los umbrales.
- No reconstruir el producto alrededor de esto hasta que el shadow mode lo valide.

## 10. Bonus — marketing
La "confianza calibrada" + "corre 100% local, tus datos no salen de tu máquina" son
**features de producto** que refuerzan tu posicionamiento de IA verificable y privada.
Se puede mostrar en el informe.

## 11. Próximo paso
Bajar **LAYA** de Hugging Face y arrancar la **Fase 0** (correrlo local, test de humo).
Después, dos pilotos posibles en shadow mode: **E3 Triage** (§5.1) o el **re-ranking
del vault** (§5·B.1). El del vault se nota más rápido en las respuestas; el de triage
es el que destraba la cobertura (§3). Se prueban con el mismo modelo, así lo bajás una
vez y lo usás en los dos frentes.

## 12. Resultados medidos — Fase 0 y Fase 1 (2026-09-26)

**Fase 0 (test de humo):** LAYA carga y corre en la PC de Damian (CPU), rutea el
español al checkpoint multilingüe solo, devuelve decisiones tipadas. ~244 ms/decisión
en CPU una vez cargado. **Funciona técnicamente.** Código: `backend/experiments/laya/`.

**Fase 1 (set semilla, 18 hallazgos: 10 reales, 8 falsos positivos):**

| Checkpoint | Accuracy | Precision (real) | Recall (real) | ECE crudo | Sev ±1 |
|---|---|---|---|---|---|
| **multilingüe (base, ruteado)** | **88.9%** | **100%** | 80% | 0.184 | 72% |
| typed-decisions (inglés) | 83.3% | 88.9% | 80% | 0.229 | 94% |

**Lecturas clave (honestas):**
1. **Medir dio vuelta la anécdota.** Con un ejemplo, typed-decisions parecía mejor;
   sobre 18 casos balanceados en español gana el **multilingüe base**. Disciplina del
   plan confirmada: se decide por datos.
2. **El modo de falla importa más que el promedio.** El multilingüe tuvo **precision
   100% pero recall 80%**: sus 2 errores fueron **falsos negativos** (vulns reales que
   marcó como falso positivo: secreto hardcodeado y falta de rate-limiting), y encima
   con confianza alta (0.65 y 0.79). En seguridad, el falso negativo es el error caro.
3. **Conclusión de diseño (importante):** dado que la confianza NO separa bien esos
   falsos negativos, el gate por confianza solo no alcanza. Política segura para el
   piloto: **LAYA puede auto-CONFIRMAR un "real" (precision 100% → confiable), pero
   NUNCA auto-descartar un "falso positivo"** — todo lo que LAYA llame FP igual pasa a
   DeepSeek/humano para segunda mirada. Asimetría de confianza.
4. **Calibración:** ECE ~0.18–0.23 = sobre-confiado, hay que ajustar temperatura con
   datos propios (esperado, avisado por el model card).
5. **Severidad:** exacta floja (primitivo `score` es el más débil), pero ±1 nivel
   razonable (72–94%). Usable como orientación, no como valor fino.

**Fase 1-bis — datos REALES (24 hallazgos del scan del propio backend: 7 reales, 17 FP):**

| Checkpoint | Accuracy | Precision (real) | Recall (real) | Sev ±1 |
|---|---|---|---|---|
| multilingüe (base) | 45.8% | 33% | 85.7% | 100% |
| typed-decisions | 33.3% | 30% | **100%** | 96% |

**Lo que enseñó (y corrige la conclusión del set semilla):**
1. **El 88.9% del set semilla estaba INFLADO por fuga de etiqueta.** Las descripciones
   sintéticas de los FP decían literalmente "es un falso positivo" y explicaban por qué
   → le regalaban la respuesta. Los datos reales (mensajes crudos del scanner) no tienen
   ese chivo, y ahí apareció el número verdadero: **~33-46%**, que coincide con el
   ~0.36 zero-shot que avisa el model card. Lección de método: **medir sobre datos
   reales, nunca sobre descripciones que uno mismo escribió con la etiqueta adentro.**
2. **Zero-shot NO sirve para este triage.** LAYA marca "real" a casi todo (18-23 de 24):
   reacciona a palabras alarmantes del mensaje, no juzga contexto. FP obvios (assert en
   test, secreto de ejemplo en doc, aviso de compatibilidad) → marcados como reales.
3. **El modo de falla se dio vuelta vs el set semilla:** ahí sub-marcaba (precision 100,
   recall 80); en real **sobre-marca** (recall 100 en typed-decisions, precision ~30).
   La dirección "sobre-marca" es la segura para un pre-filtro (no tapa vulns), pero al
   marcar el ~96% como real casi no filtra → sin fine-tuning no ahorra trabajo.
4. **Severidad ±1 sí es usable** (96-100%) incluso zero-shot.

**Fase 1-ter — MÁXIMO contexto (código real inyectado + criterios ricos), 24 reales:**

| Checkpoint | Accuracy | Precision | Recall | ECE |
|---|---|---|---|---|
| multilingüe (base) | 29.2% (⬇ de 45.8%) | 22% | 57% | 0.376 |
| typed-decisions | 29.2% | 29% | 100% | 0.299 |

**Resultado decisivo:** darle el **código real + criterios ricos EMPEORÓ** al base
(45.8 → 29.2) y no movió a typed-decisions (marca los 24 como "real"). Con el código,
a un secreto de EJEMPLO en una nota (FP obvio) lo marcó "real" con **0.98 de
confianza**: más seguro y más equivocado. **Conclusión: el contexto crudo NO es la
palanca para LAYA.** Es un clasificador de 421M, no un razonador; volcarle código lo
satura, no lo ilumina.

**Reencuadre estratégico (lo que esto decide):**
- ❌ **Inyección de contexto crudo:** callejón sin salida para LAYA. Probado.
- ✅ **Estructura tipada (la palanca real):** no darle código, sino **features
  extraídas** por nosotros (`es_archivo_test`, `entrada_usuario_llega_a_sink`,
  `es_ejemplo_en_doc`, `secreto_literal_vs_env`, `mitigacion_presente`…). Con features
  limpias, hasta **reglas deterministas** resuelven los casos obvios (test → FP; ejemplo
  en .md → FP; aviso de compat → FP) con 100% de explicabilidad. Y sirve a TODA la
  Brigada (E3/E5/E6), no solo a LAYA.
- ⚠️ **Fine-tuning de LAYA:** sigue siendo posible, pero ahora se ve como mucho trabajo
  (etiquetar cientos + entrenar + mantener) para un modelo chico que un combo
  **reglas + DeepSeek** podría igualar o superar. **Decidir por datos, no por inercia
  (sunk cost).** Reconsiderar solo si, tras estructura+reglas, queda una franja
  ambigua donde un clasificador barato entrenado gane a las reglas y valga el costo.

**Arquitectura candidata (revisada):** piso 1 = **extractor de features tipadas +
reglas** (barato, explicable, cubre el grueso del ruido) → piso 2 = **DeepSeek** para
lo genuinamente ambiguo. LAYA queda en observación, no en el camino crítico.

## Fuentes
- LAYA (Convai): model card `convaiinnovations/laya` en Hugging Face · variante
  multilingüe `convaiinnovations/laya-multilingual` · github.com/NandhaKishorM/laya ·
  eesel.ai/blog/laya-ai (Apache 2.0, 2026-09-18).
- Jev (TypeSafe): typesafe.ai/blog/introducing-system-one-models-and-jev.
