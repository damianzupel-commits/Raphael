# Ideas pendientes de Raphael

> Capturadas en sesiones con Claude. No implementadas todavia.

---

## 2026-10-31 — Jefe de brigada (capa de mando intermedia)

**Idea (Damian):** que cada brigada tenga un **jefe de brigada** con el que el **orquestador (Gran Sabia / Raphael) habla directamente**. El orquestador NO habla con cada skill/soldado uno por uno, sino que delega al jefe, y el jefe comanda las skills de su brigada.

**Por que importa:** jerarquia clara orquestador -> jefe -> skills. Reduce lo que el orquestador tiene que manejar en paralelo, y encaja con:
- el `ops_supervisor` que ya existe (supervisor Sonnet de la brigada Operaciones) -> generalizar: un jefe por brigada.
- el graph-orchestrator / concurrencia del SPEC-MEJORAS-RAPHAEL.

**En la UI (cuando toque):** un nodo de "jefe" entre el nucleo y las hojas (skills) de cada rama. El orquestador hablaria con esos nodos jefe.

**Estado:** solo anotado. Pendiente de disenar. No tocar hasta terminar la estetica.
