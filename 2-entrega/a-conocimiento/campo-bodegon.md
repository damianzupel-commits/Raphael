# Captura de campo (piloto del bodegón)

Para que Damián anote desde el celular, durante el turno, todo lo que ve en un negocio, y después tenga el resumen del día y un expediente consultable. Código: `raphael_personal_api/campo.py` (lógica) y `campo_rutas.py` (HTTP); pantalla: pestaña **Campo** de la web de Raphael personal (la misma que se abre en el celular por Tailscale). Tests: `servidor/api/tests/test_campo.py`.

## Cómo se usa (el lunes)
1. En el celular, abrí Raphael (la dirección de Tailscale con https; el micrófono solo anda con https o en la PC) y entrá a **Campo**.
2. **Nuevo** → nombre del negocio (una vez). Después elegís el negocio en la lista.
3. Durante el turno: escribir una nota, **🎤 Grabar** (se transcribe si la voz está instalada) o **📷 Foto**. El tema se elige con los botones (Salón, Cocina, Caja, Personal, Clientes) o queda en **Auto** y se deduce por palabras.
4. Al cerrar: **Cierre del día** con las 3 cosas que más tiempo o plata hicieron perder, y **Resumen del día**.
5. **Preguntarle al expediente**: «¿cuántas veces faltó stock?» devuelve el conteo por día y las notas. **Ver expediente / Bajar .md** da todo ordenado por tema, para el diagnóstico.

## Dónde queda
`<datos>/campo/<negocio>/` en la PC: `diario/AAAA-MM-DD.jsonl` (una línea por nota), `media/` (audios y fotos tal cual), `resumenes/AAAA-MM-DD.md`. Nada sale de la PC.

## Reglas
- La IA que arma el resumen con IA local o contesta preguntas se pide siempre **privada** (solo modelo local: LM Studio u Ollama). Sin modelo prendido cae a reglas y lo dice; nunca lo manda a la nube.
- Un audio se guarda siempre, aunque la transcripción falle (`POST /api/v1/campo/transcribir/{id}?negocio=` la reintenta).
- Los nombres de archivo los pone el código; el negocio, el tema y el tipo de archivo se validan.
- Es captura y orden de lo que Damián observa. El diagnóstico lo hace él: el resumen por reglas es tosco (ordena por palabras de pérdida) y por eso el cierre del día manda cuando existe.

## Límites conocidos
- Las fotos se guardan y se listan, pero Raphael todavía no las describe (haría falta un modelo con visión local).
- La app Android nativa no tiene esta pantalla todavía; en el celular se usa la web.
- No está integrado con la brigada Memoria (vault): vive aparte a propósito, para no pisar el hilo del cerebro compartido. Cuando ese diseño esté, cada nota puede pasar al vault con `memoria.captura`.
- Sin probar en la PC de Windows ni con el micrófono real del celular; sí probado en navegador de celular simulado.

## Endpoints (`/api/v1/campo`, todos con sesión)
`GET /` · `POST /negocios` · `POST /nota` · `POST /voz?negocio&tema` (audio crudo) · `POST /foto?negocio&tema&texto` (imagen cruda) · `POST /cierre` · `PATCH /nota/{id}` · `GET /notas?negocio&dia&tema&q` · `GET /media/{archivo}?negocio` · `GET /resumen?negocio&dia&ia` · `POST /preguntar` · `GET /expediente?negocio` · `POST /transcribir/{id}?negocio`.
