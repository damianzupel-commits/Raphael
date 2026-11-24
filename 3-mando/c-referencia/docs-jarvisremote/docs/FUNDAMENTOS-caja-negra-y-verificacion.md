# La caja negra de la IA, el grokking y la verificación — explicado a fondo (con fuentes)

> Escrito el 2026-09-26, verificado contra los papers originales. Nace de la
> discusión sobre el video "¿Por qué ya no entendemos a la IA?" y la pregunta de
> Damian: "¿lo esquivo o lo resuelvo?". La respuesta corta: son **dos problemas
> distintos**, y Raphael ataca el que sí se puede — y lo hace **como la ciencia dice
> que funciona.**

---

## Los dos problemas (no confundirlos)

- **A) Interpretabilidad:** entender qué pasa DENTRO del modelo, por qué llega a una
  respuesta. Frontera de investigación abierta.
- **B) Confiabilidad:** poder confiar en la salida y saber por qué, sin abrir el
  modelo. **Este es el que le importa a un cliente, y el que Raphael resuelve.**

---

## 1. El problema de la caja negra

Sabemos construir y entrenar estos modelos (la arquitectura la entendemos), pero
**no podemos leer directamente por qué** una red de miles de millones de parámetros
decide lo que decide. No es magia: es que las representaciones internas son enormes,
distribuidas y no vienen "etiquetadas". Un buen resumen (de un comentario del propio
video): para los informáticos la "caja negra" nunca fue un misterio místico, sino una
**capa de abstracción** — usamos cosas sin entender cada engranaje.

## 2. Grokking — "comprensión repentina"

- **Qué es:** un modelo entrena, parece que solo **memoriza** (le va bien en
  entrenamiento, mal en datos nuevos)… y de golpe, mucho después, **generaliza** de
  verdad. El salto es abrupto y tardío.
- **Fuente original:** Power, Burda, Edwards, Babuschkin, Misra (OpenAI), *"Grokking:
  Generalization Beyond Overfitting on Small Algorithmic Datasets"*, 2022 —
  arXiv **2201.02177**.
- **El dato clave que el video (y el miedo) omite:** el grokking **se explicó**.
  Neel Nanda et al., *"Progress measures for grokking via mechanistic
  interpretability"*, 2023 (arXiv **2301.05217**) abrieron la red y encontraron que,
  durante el "grokking", el modelo pasaba de memorizar a **implementar un algoritmo
  real** (aritmética modular vía transformadas de Fourier) dentro de sus pesos.
- **Conclusión honesta:** no es que la máquina "despertó". Es un fenómeno de
  aprendizaje, real y fascinante, pero **ya parcialmente entendido**. Salto de
  comportamiento, no de conciencia.

## 3. Capacidades "emergentes" — el debate honesto

- **La afirmación (Wei et al., Google, 2022, TMLR):** al aumentar la escala, aparecen
  de golpe habilidades que los modelos chicos no tenían ("emergencia"), de forma
  brusca e impredecible.
- **La crítica (Schaeffer, Miranda, Koyejo, Stanford, 2023, NeurIPS — arXiv
  **2304.15004** *"Are Emergent Abilities of Large Language Models a Mirage?"*):**
  buena parte de esos "saltos" son un **artefacto de cómo se mide.** Con métricas
  discontinuas (acierto/error exacto) ves un salto brusco; con métricas continuas, la
  mejora es **suave y predecible**. Encontraron que >92% de las "emergencias"
  reclamadas aparecían bajo dos métricas puntuales (Multiple Choice Grade / Exact
  String Match).
- **Conclusión honesta:** la "emergencia mágica" está **en disputa académica**. Hay
  mejora real con la escala, pero mucho del drama es elección de gráfico. Ojo con los
  que extrapolan pánico de una curva.

## 4. Abriendo la caja DE VERDAD — interpretabilidad mecanicista

El campo que sí intenta abrir el modelo, con éxito **parcial pero real** (lo lidera
Anthropic, los que hacen a Claude):

- **Superposición / polisemantia:** hay más conceptos ("features") que neuronas, así
  que la red los guarda **superpuestos** — una neurona codifica varias cosas a la vez.
  Por eso mirar neurona por neurona no alcanza.
- **La técnica que destrabó esto — Sparse Autoencoders (SAE):** descomponen esa
  superposición en **features monosemánticas** (una idea por unidad, interpretable).
- **El hito:** Anthropic, *"Scaling Monosemanticity: Extracting Interpretable Features
  from Claude 3 Sonnet"*, 2024 (transformer-circuits.pub). Extrajeron millones de
  features interpretables de un modelo grande real. El ejemplo famoso: encontraron la
  **feature del "puente Golden Gate"**; al amplificarla, Claude se obsesionaba y metía
  el puente en cualquier respuesta. **Prueba de que la caja se puede abrir y hasta
  manipular** — de a pedacitos.
- **Circuitos:** grupos de neuronas + cabezas de atención que implementan una función
  concreta (recuerdo de datos, identificación de objetos, etc.).
- **Estado:** avanza rápido pero está **lejísimos** de "entender el modelo entero".
  Por eso, para un producto, **no podés depender de esto todavía.**

## 5. El otro problema: confiabilidad y verificación (lo tuyo)

Como no podemos abrir el modelo del todo, la pregunta práctica es: **¿cómo confío en
la salida?** Acá hay un hallazgo académico que es CLAVE para Raphael:

- **Alucinación:** los modelos a veces inventan con seguridad. Conocido y medido.
- **El hallazgo que te valida — Huang et al. (Google/UIUC), *"Large Language Models
  Cannot Self-Correct Reasoning Yet"*, ICLR 2024 (arXiv **2310.01798**):** cuando un
  LLM intenta **auto-corregirse solo, sin información externa** ("pensá de nuevo"), en
  razonamiento **no mejora, y a veces EMPEORA.**
- **PERO** —y esto es lo importante— el mismo trabajo aclara que el límite es *sin
  feedback externo*. Cuando la corrección se **ancla a una fuente de verdad externa**,
  sí funciona.

## 6. Qué significa para Raphael (la bajada)

1. **No resolvés A (interpretabilidad).** Nadie lo hizo; no te mientas ni prometas eso.
2. **Sí resolvés B (confiabilidad), y lo hacés BIEN según la ciencia.** Tu **Catador**
   no le pide a la IA "pensá mejor" (eso NO funciona, Huang 2023). La hace **verificar
   su salida contra el CÓDIGO REAL** — feedback externo, la única forma que la
   evidencia dice que sí mejora. **Tu diseño está académicamente alineado.**
3. **QW-3 (citar la fuente de cada afirmación) es tu versión de "interpretabilidad
   práctica":** no abrís el modelo, pero hacés que **muestre su trabajo anclado a
   evidencia** (archivo:línea). El humano puede seguir el "por qué" sin abrir la red.
4. **Reforzar con consenso:** cruzar varias pasadas/agentes que deban coincidir baja
   más el error (misma familia de ideas que la verificación externa).

**Frase para tu pitch, ahora con respaldo:** *"No te pido que confíes en una caja
negra. La IA muestra su trabajo y se verifica contra tu código real — que es,
según la investigación, la única forma que de verdad funciona."*

---

## Fuentes (papers originales)
- Grokking: Power et al., 2022 — arXiv 2201.02177.
- Grokking explicado: Nanda et al., 2023 — arXiv 2301.05217.
- Emergencia: Wei et al., 2022, TMLR.
- Emergencia = ¿espejismo?: Schaeffer et al., 2023, NeurIPS — arXiv 2304.15004.
- Interpretabilidad mecanicista: Anthropic, *Scaling Monosemanticity*, 2024 — transformer-circuits.pub.
- Límite de la auto-corrección: Huang et al., 2023/ICLR 2024 — arXiv 2310.01798.
