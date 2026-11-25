# arXiv

- **Brigada:** 10-ingesta · Ingesta (chat 10)
- **Tipo:** existente
- **Qué hace:** Ingiere papers de arXiv.

## Código nuevo (harness v2)
En `1-harness/c-brigadas/10-ingesta/b-codigo/src/raphael_ingesta/`: `cooks/arxiv.py` y `adapters/arxiv.py` (portado de `arxiv_source.py`).

Acciones: `ingerir_paper`, `buscar_arxiv`, `vigilar`. La búsqueda ya trae el abstract. El parseo del Atom está probado; el pedido real no.

## Dónde estaba el código viejo
Rutas relativas a `3-mando/c-referencia/ingestion/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/ingestion/arxiv_source.py`
- `app/ingestion/sources.py`
- `app/ingestion/base.py`

## Notas
Agrupación propuesta según nombres de archivo.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código está en `b-codigo/src/`; sus tests en `c-salud/pruebas/`. El código existente está como referencia, solo lectura, en `raphael\3-mando\c-referencia\ingestion\`.
