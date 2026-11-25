# raphael-legales · Brigada Legales (harness v2)

Prepara borradores y revisa riesgos para un pyme argentino. **No da asesoramiento legal ni reemplaza a un abogado**: todo lo que produce lo dice, sale como BORRADOR y la brigada no tiene ninguna acción que firme, envíe o presente. Se monta por su `manifest.yaml` (contrato 2.1) y solo importa `raphael_core` y la stdlib (más pydantic y pyyaml): ninguna otra brigada.

## Cocineros y acciones
| Cocinero | Qué hace | Acciones (nivel) |
|---|---|---|
| `documentos` | Borradores desde plantillas (privacidad, términos, presupuesto, contrato, carta) con los datos del negocio; lo que falta sale `[COMPLETAR: x]`, lo que hay que confirmar `[VERIFICAR: ...]` | `generar_borrador` (automático) |
| `cumplimiento` | Checklist de 15 ítems (datos personales, consumidor, facturación, Meta/WhatsApp), parte deducido del archivo; consulta las fuentes oficiales y avisa si la página cambió | `verificar_norma` (automático) |
| `riesgos` | Revisa textos antes de publicar (14 reglas, más segunda lectura con modelo si hay). Lo piden Gestión y Contenido por el comando `revisar` o el evento `revision.pedida` | `revisar_texto` (automático) |
| `archivo` | Versiones de documentos y consentimientos/bajas. Emitir deja una versión inmutable | `registrar_consentimiento`, `registrar_baja` (automáticos); `emitir_documento`, `borrar_registro` (aprobación, irreversible) |

## Adaptadores (lo enchufable)
- **Fuentes normativas** (`sources.py`): `real` (HTTPS a páginas oficiales públicas, sin clave), `mock` (tests) y `off`. Se elige con `fuentes.modo` o `LEGALES_FUENTES_MODO`. La consulta prueba que la fuente responde, que es la norma esperada y si cambió desde la última vez; **no** prueba que un resumen siga vigente. Sin red queda "sin verificar" y lo dice.
- **Modelo de IA**: el del harness (`ctx.ai`). Opcional: segunda lectura de riesgos (solo agrega notas) y redacción del cuerpo de una carta. Sin clave, reglas y plantillas, y lo avisa. El texto de terceros va delimitado como dato.
- **Datos del negocio**: `negocio.*` de la config o variables `LEGALES_NEGOCIO_*`. Plantilla: `legales.env.plantilla`.

## Config (`installation.brigades.legales.config`)
```yaml
negocio: {nombre: ..., cuit: ..., domicilio: ..., email: ..., telefono: ..., jurisdiccion: Argentina}
fuentes: {modo: real, timeout: 10, dias_vigencia: 30, urls: {}}
checklist: {respuestas: {dp-derechos: cumple}}
riesgos: {ia: true, palabras_extra: [{patron: "...", mensaje: "...", severidad: media}]}
proveedor_ia: "un proveedor externo de modelos de IA (OpenRouter)"
```
La política de privacidad dice que los mensajes se procesan con un tercero de IA (decisión del 24 nov: Legales lo informa).

## Probar
```
cd ..\c-salud\pruebas
python -m pytest        # usa src\ y raphael-core del proyecto (o RAPHAEL_CORE_SRC)
```
Si cambiás `manifest.yaml`, copialo a `src\raphael_legales\manifest.yaml` (un test lo verifica).
