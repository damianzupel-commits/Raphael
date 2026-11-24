Soy Damián (Rosario, Argentina). Hablame en castellano rioplatense, con voseo, directo y corto.

Raphael son dos productos con un mismo núcleo:
- Personal (JarvisRemote): corre solo en mi PC y puede tener capacidades peligrosas.
- Empresas: público, en la nube, lleva una empresa casi entera. Nunca cero humanos: lo irreversible lo aprueba una persona.

Arquitectura: un harness (la base, sin brigadas concretas), un orquestador parado encima, y brigadas que se montan o desmontan por configuración. Las brigadas nunca se importan entre sí: todo pasa por el orquestador. Raphael Empresas es una brigada, no la base: para mi clienta se instala harness + orquestador (con el rol de Secretaria) + brigada Empresas; en mi personal la Secretaria es jefa de esa brigada y reporta al orquestador maestro. Harness v2: se portan y unifican los dos motores existentes.

Cada sesión de este proyecto es el agente de UNA pieza (ver 3-mando\a-conocimiento\PIEZAS.md). Trabajás solo en tu pieza. Si algo toca otra, anotalo como "pendiente para <pieza>" en vez de resolverlo.

Carpeta de trabajo única: D:\Raphael Ultimate\raphael (todo lo anterior está archivado en D:\Raphael Ultimate\_archivo y no se usa). Al empezar leé raphael\CONTEXT.md y el README de la rama de tu pieza (raphael\1-harness\c-brigadas\<NN-nombre>\README.md, raphael\1-harness\README.md o raphael\2-entrega\README.md), y su log (a-historia\log.md en cada brigada). Esos archivos son la fuente de verdad; si difieren de lo que tengas en contexto, ganan los de la carpeta.

Reglas:
- Código nuevo en la rama de tu pieza (b-codigo\ para el código, c-salud\pruebas\ para los tests, a-historia\ para lo que hay que saber); raphael\3-mando\c-referencia\ es código viejo de solo lectura. Los originales (Documents\raphael, Documents\JarvisRemote) no se tocan. Los push los hago yo.
- Código con nombres en inglés; documentación y mensajes en español rioplatense.
- No leas ni imprimas .env ni claves.
- No inventes: si no verificaste algo del código, decilo.
- Para APIs de Meta, precios o leyes argentinas, buscá fuente actual.
- Acciones sin vuelta atrás: proponelas, no las hagas.
- Al cerrar una sesión escribí un "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió) en el log de tu pieza.
- En Estudio y Divague: sin código ni planes formales salvo que los pida.
