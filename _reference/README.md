# _reference/

Código existente de JarvisRemote y de los repos viejos de Empresas, de **solo lectura**. Es la fuente de la que se porta cada brigada al harness v2; no se edita ni se importa desde el código nuevo.

- `<brigada>/`: una carpeta por brigada (`security`, `antimalware`, `research`, `geo-intel`, `memory`, `ingestion`, `trading`, `operations`, `self-repair`, `content`, `business`, `legal`), con su `INDICE-CODIGO.md` (origen, commit y conteo de archivos).
- `core/`, `orchestrator/`: los dos motores y los dos orquestadores previos (JarvisRemote y Empresas 0.4).
- `servidor-app-installer/`: raphael-servidor, relay, central, android, instalador y tray-app de JarvisRemote.
- `_unclassified/`: partes de `backend/app`, tests y raíz de JarvisRemote sin brigada asignada. Decidir a cuál pertenecen o descartar.
- Filtros de la copia: sin `.env`, claves, bases, logs, vaults, binarios ni archivos de más de 2 MB.
