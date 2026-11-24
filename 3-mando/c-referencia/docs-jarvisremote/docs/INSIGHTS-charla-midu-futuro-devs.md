# INSIGHTS — charla de midudev "El futuro para los devs" (Nerdearla) → Raphael

> Creado el 2026-09-26. Cruce de la charla de Miguel Ángel Durán (midudev) en
> Nerdearla con la estrategia de Raphael. Fuente:
> https://www.youtube.com/watch?v=jjheLyrTG4Y (43 min).
>
> **Encuadre:** documento de análisis/estrategia. Cruza con el experimento
> `EXPERIMENTO-JEV-motor-de-decisiones.md` (lab) y con el material de marketing en
> `Desktop/Damian/Raphael-Auditor-Producto/`.

---

## 1. Resumen de la charla
Tesis honesta: **la programación no murió, se automatizó y cambió de forma.** El
código pasó de manual a automático, pero programar nunca fue solo codificar. Puntos:

- **Paradoja de Jevons:** cuando algo se abarata/accede más, se consume más. Por eso
  hoy se programa más que nunca (récord de commits/PRs/repos), no menos.
- **Los modelos son un commodity.** Cambiar un modelo por otro da casi lo mismo en el
  90-95% de los casos. El negocio no está en el modelo, sino en **saber implementarlo**
  en empresas.
- **Self-hosting = ahorro brutal:** Shopify -99% (de US$5,5M/año a $3.000 con un Qwen
  propio), Palantir -95% (fine-tuning de open-source superando a los frontera en 48h),
  Spotify -95%.
- **La IA no suple la ignorancia:** "te hace creerte listo, pero no lo sos" — no sabés
  si el código tiene vulnerabilidades, si es mantenible, si guarda datos sensibles mal.
- **Jev (modelo de decisiones System-1):** demo en vivo clasificando mensajes y jugando
  al Super Mario. Primitivos: `score`, `choice`, `noul`. **Clave:** al Mario le pasa un
  **objeto con el estado** (no la imagen), porque el modelo no razona sobre material
  crudo.
- **Lo nuevo:** WebMCP (que las webs le declaren a la IA qué pueden hacer, sin
  scrapear), MCP UI (respuestas visuales/interactivas), IA 100% local en el navegador.

## 2. Cruce con Raphael

### 2.1 Lab — valida el giro de hoy (ver [[EXPERIMENTO-JEV-motor-de-decisiones]])
El Super Mario es la prueba viva de nuestra conclusión: el modelo de decisiones
**no razona sobre datos crudos** (por eso midu le pasa un objeto de estado, no píxeles).
Hoy nosotros medimos que darle a LAYA el **código en bruto EMPEORÓ** el triage; la
palanca es la **estructura tipada** (features limpias). La charla lo confirma desde otro
ángulo: *funciona cuando le das el estado estructurado, no la materia prima.* Los tres
primitivos que muestra (score/choice/noul) son los mismos que probamos.

### 2.2 Producto/estrategia — refuerza el diferencial
- **"Los modelos son commodity; el valor está en implementarlos."** El moat de Raphael
  no es DeepSeek (intercambiable), es **la Brigada + la verificación + el flujo**. Regla:
  invertir en el pipeline, no en el modelo.
- **Self-hosting -95/99% (Shopify/Spotify/Palantir).** Valida el diferencial central de
  Raphael: **corre 100% local, sin costo recurrente de API, los datos no salen de la
  máquina.** Casos reales de empresas top que respaldan el argumento.
- **Palantir fine-tuneó open-source y ganó a los frontera en 48h (-95%).** Es el camino
  de fine-tuning de LAYA que dejamos parkeado — la charla muestra que es una estrategia
  **real y probada**, no humo. Refuerza reconsiderarlo con disciplina (labels propios +
  set held-out).

### 2.3 Marketing/ventas — el pitch validado en público
- **"La IA no suple la ignorancia"** → es, palabra por palabra, la propuesta de valor de
  Raphael, dicha por alguien con 3M de seguidores. El código vibe-codeado shippea
  vulnerabilidades que el que lo hizo no ve. Raphael las encuentra. → Post (ver
  `10-CONTENIDO-Y-MUESTRA-GRATIS/post-11/`).
- **"Resolvé los problemas de la gente que te rodea — la panadería, la pizzería."** Es el
  go-to-market de PyMEs (Blindaje PyME). La oportunidad está en las empresas que "no
  tienen ni idea".

## 3. Acciones concretas (destiladas)
1. **Lab:** al diseñar el extractor de features tipadas, tener el Mario como modelo
   mental: definir el "objeto de estado" del hallazgo (test/prod, entrada→sink, ejemplo
   en doc, secreto literal/env, mitigación) igual que midu define el estado del juego.
2. **Ventas:** sumar a los materiales el ángulo "modelos = commodity, el valor es la
   implementación local y verificada" y los números de ahorro (-95/99%) como prueba.
3. **Marketing:** publicar el post-11 (la IA no suple la ignorancia).
4. **Reconsiderar** (no ahora) el fine-tuning de LAYA a la luz del caso Palantir, con la
   disciplina ya escrita en el experimento.

## 4. Semilla futura — WebMCP como superficie de auditoría
midu marca que WebMCP "trae un problema de seguridad debajo del brazo". A medida que las
webs expongan acciones vía WebMCP, aparece una **nueva superficie de auditoría**
(acciones expuestas, autenticación, abuso). Raphael se podría especializar ahí más
adelante. Guardado como semilla, no como tarea.

## Fuente
- midudev, "El futuro para los devs", Nerdearla — https://www.youtube.com/watch?v=jjheLyrTG4Y
