# Para el coordinador (pieza 07)

## gate.py (3-mando/b-herramientas)
Sumar la suite: `"investigacion": ROOT / "1-harness" / "c-brigadas" / "07-investigacion" / "c-salud" / "pruebas"` en `SUITES`. 68 tests.

## modelos.yaml (harness)
Agregar `investigacion` a `private:` (hoy `[memoria-cerebro, investigacion-forense]`) y poner el modelo local (Ollama o LM Studio, `localhost`) en el escalón `local`. La brigada igual llama con `private=True`, así que sin eso nada sale a la nube, pero no hay modelo hasta que exista el local.

## ESTADO.md
Investigación (07): brigada 2.0.0 portada, contrato en verde, 68 tests con adaptadores simulados. Sin probar con Brave/SearXNG reales ni modelo local real.

## LIENZO-DAMIAN.md (plantilla: `b-codigo/investigacion.env.plantilla`)
| Qué | Dónde se saca | Dónde se pega | Qué se prueba |
| --- | --- | --- | --- |
| `BRAVE_SEARCH_API_KEY` (o `SEARXNG_URL`) | brave.com/search/api (plan gratis) | el `.env`/pantalla de Configuración | comando `proveedores` (configurado: sí) y `investigar` con una pregunta |
| Modelo local (Ollama o LM Studio) | ollama.com / lmstudio.ai | `modelos.yaml`, escalón `local` | `investigar` devuelve `modelo: true` |
| `INVESTIGACION_LOG_KEY` (opcional) | una frase larga inventada por Damian | el `.env` | `verificar_log` dice `signed` > 0 |
| `inbox_dir`, `reports_dir`, `artifacts_dir` (opcionales) | carpetas de la PC | config de la brigada | ingerir un archivo de prueba; exportar un informe |
| Temas a vigilar | Damian | comando `seguir` | `revisar` |
Opcional: `pip install pypdf python-docx Pillow` para PDF, Word y EXIF.
