# packages/

El núcleo de Raphael. No contiene brigadas.

- `core/` (raphael-core): el harness. Contrato versionado, cargador de manifiestos, runtime, bus de eventos, almacén por brigada, Policy Engine con autonomía configurable, modelos por rol, auditoría. Su README explica cómo se hace una brigada montable.
- `orchestrator/` (raphael-orchestrator): el orquestador. Se para sobre el harness: mando, voz, ruteo, reparto por DAG, confirmación de acciones, Secretaria genérica y avisos proactivos.

Estado de la copia: instantánea del 24 nov 2026 (96 + 30 archivos, sin `.venv`, `.datos` ni claves). Ver `../README.md` (migración).
