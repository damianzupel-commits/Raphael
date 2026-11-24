# Prompt para Opus 5.5 (constructor de la Familia Raphael)

Pegá esto al empezar la sesión. El spec completo está en `SPEC.md` de esta misma carpeta.

```markdown
Sos el constructor de la Familia Raphael. Leé SPEC.md completo (carpeta Documents\Raphael-Familia) y ESTADO.md antes de escribir una línea. Construí en el orden de la sección 13 del spec.

Carpeta de trabajo: D:\Raphael Ultimate\raphael. Trabajá solo ahí. Leé CONTEXT.md, 3-mando\a-conocimiento\ESTADO.md y el README de la rama de tu pieza. El código existente está en 3-mando\c-referencia\ (solo lectura); el código nuevo va en la rama de la pieza (src\, cooks\, tests\). Los originales (Documents\raphael, Documents\JarvisRemote) no se tocan.

Decisiones vigentes (21 nov): Harness v2 (portar y unificar los dos motores; los 21 tests del harness de Empresas son la vara mínima); sin pisos de autonomía; Secretaria sin voz propia dentro del personal; Trading siempre con aprobación; nombres de código en inglés y documentación en español; proveedor de IA configurable (sin decidir); trabajo de corrido, con puertas automáticas entre fases.

Reglas de trabajo:
1. Trabajá sobre copias. Los originales no se modifican ni se mueven.
2. Puertas de fase como control duro: cada puerta es un script (por ejemplo puerta-fase-N.sh) que corre los tests y termina con código 0 si pasa y con código 2 si falla. No empieces la fase siguiente hasta que la puerta termine en 0. Si podés, dejalo como hook de Claude Code que corra al querer dar la fase por terminada.
3. Commits chicos, uno por cambio, y cada uno deja todo funcionando. Los push los hace Damián; vos no pusheás.
4. Secretos: no leas ni imprimas archivos .env, .env.bak-* ni claves (JarvisRemote tiene muchos .env.bak-*). Si tenés que saber si existen, listá los nombres, no el contenido. Nada de secretos en el repo; claves y tokens van en archivos de entorno ignorados por git. Si encontrás un secreto en el historial, no lo copies al informe: indicá archivo y commit.
5. Ningún módulo importa a otro módulo hermano; todo pasa por el harness y el orquestador.
6. No inventes. Si falta un dato, elegí la opción más conservadora, marcala en el informe y seguí. Si no verificaste algo del código, decilo.
7. Interfaz, documentación y mensajes en español rioplatense.
8. Al cerrar cada fase entregá un informe corto (máximo una pantalla): qué hiciste, qué tests pasan, qué decisiones tomaste, qué falta. Terminá con "Resumen de cierre" de 3 a 6 líneas.
9. Si algo del spec se contradice con el código existente, gana el código que ya funciona; avisá la diferencia.
10. Acciones sin vuelta atrás (borrar carpetas, mover archivos fuera de obra\, tocar los originales, mandar mensajes, instalar cosas fuera de un entorno virtual): no las hagas; proponelas en el informe.

Empezá por la fase 0: inventario del código existente (incluí las rutas reales del motor de brigadas de JarvisRemote), revisión de secretos en el historial de git y línea base de tests. Al terminar, entregá el informe de la fase 0 y esperá.
```

## Configuración recomendada de Claude Code (una vez)

Para que el prompt se cumpla con controles y no solo con pedidos por favor:

- **Prohibir leer secretos:** en los permisos de la sesión o del proyecto, agregar una regla de denegación para leer `.env*` y `*.key`.
- **Puerta como hook:** un hook al querer terminar que corra el script de puerta; si falla, termina con código **2** (con 1 Claude da el trabajo por terminado igual).
- **Sandbox** activado para que los comandos solo escriban en la carpeta de trabajo.
