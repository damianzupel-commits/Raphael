# Autorreparación · mantenimiento
- `b-codigo/scripts/sync_manifest.py`: copia el manifiesto del paquete al de desarrollo. Correrlo después de editar `src/raphael_selfrepair/manifest.yaml` (la puerta falla si quedan distintos).
- Propuestas viejas: no se borran solas (quedan como historial: aplicadas, revertidas, rechazadas, descartadas). Se exportan con el desmontaje (`uninstall.export`).
- Si el archivo de un arreglo cambió y `revertir` dice "revisalo a mano": usá el commit guardado en la propuesta (`commit`) con `git revert`.
