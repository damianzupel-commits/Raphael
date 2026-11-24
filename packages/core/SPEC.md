# SPEC · Harness

Chat 1 · Actualizado 21 nov 2026

## Objetivo
Núcleo común: contrato versionado, cargador de módulos por manifiesto, bus de eventos, almacén por espacio, políticas de autonomía configurables, modelos por rol, aislamiento de fallos y suite de contrato. Harness v2 = infraestructura de Empresas + motor de brigadas de JarvisRemote.

## Dónde corre
PC y VPS.

## Convenciones
- Código con nombres en inglés; documentación y mensajes al usuario en español rioplatense.
- Proveedor de IA configurable por rol y por plan; hoy sin decidir.

## Reglas
- Se parte de lo que ya anda: se porta, no se tira. Los 21 tests de raphael-harness son la vara mínima del harness v2.
- Contrato con versionado semántico (hoy: entero CONTRATO = 1 en Empresas y VERSION = 1 en JarvisRemote).
- Políticas sin pisos fijos (decidido 21 nov): cualquier acción puede bajarse hasta automático, con advertencia y auditoría al subir algo con gasto o irreversible. El Policy Engine de Empresas hoy solo permite endurecer y tiene pisos (devolver_dinero, confirmar_pago): hay que cambiarlo al portarlo.
- Mapear los roles de modelo: spec (mando, voz, ruteo, jefe, cocinero, efimero) vs Empresas (intencion, redaccion, resumen, secretaria) vs JarvisRemote (variables de entorno).
- El contenido de terceros (mensajes, páginas, archivos subidos) es dato, nunca instrucción.
- Ninguna brigada importa a otra: todo intercambio pasa por el harness y el orquestador.
- Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación (el nivel es configurable).
- Sin modelo o sin red, la brigada cae a reglas y avisa; nunca inventa.
- Cada acción declara su nivel de autonomía (automatico, aprobacion, humano) en el manifiesto.

## Estado
Existen dos motores distintos. Harness v2 sin empezar.

## Criterios de aceptación (mínimos)
- Pasa la suite de contrato del harness v2 (manifiesto válido, healthcheck, montar y desmontar).
- Ningún import de otra brigada (chequeo AST).
- Los tests existentes de esta brigada se portan y pasan.
- Las acciones con efecto no se ejecutan sin su nivel de autonomía.
