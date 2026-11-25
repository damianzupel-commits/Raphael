# Entrevista a la clienta · Raphael Empresas

Qué es: las preguntas que Damián le hace a la clienta (vendedora de ropa a medida, sin PC) después de mostrarle la demo de Mi Tienda IA, y dónde se anotan sus respuestas. Con esto se carga su perfil y se ajustan los módulos antes de entregarle Raphael funcionando.

Cómo se usa:
1. Damián hace las preguntas por orden (la ★ marca las que bloquean la entrega) y anota la respuesta en la columna **Respuesta**, tal cual la dijo.
2. Cada pregunta trae el **Supuesto** con el que se arma hoy el perfil. Es un supuesto, no un dato: ninguno se verificó con ella. Si la respuesta lo contradice, manda la respuesta.
3. Con las respuestas completas se corrige `a-historia/perfil-clienta.borrador.yaml`, se pasa a instalación con `scripts/perfil_a_instalacion.py` y se ajustan los módulos (sección 9).

Estado al 24 nov 2026: **sin respuestas todavía**. Todo lo que dice "Supuesto" está por confirmar.

Tono de la entrevista: corto, rioplatense, con ejemplos de su rubro. Mostrar, no explicar la arquitectura.

## 0. Datos de ella y del negocio
| # | Pregunta | Supuesto (sin confirmar) | Respuesta |
| --- | --- | --- | --- |
| 0.1 ★ | ¿Cómo se llama el negocio y cómo querés que te nombre Raphael a vos cuando le habla a tus clientes? | Nombre y dueña a completar; hoy hay datos del piloto (Taller Ejemplo / Ana) | |
| 0.2 | ¿Dónde estás (ciudad, zona)? ¿Atendés en un taller/local o a domicilio? | Rosario, zona centro, con turnos de prueba en el taller | |
| 0.3 | ¿Trabajás sola o hay alguien más que atienda mensajes, pagos o entregas? | Sola; una sola persona aprueba | |
| 0.4 | ¿Cómo hablás con tus clientas: de vos, con emojis, más formal? Pasame dos mensajes tuyos reales. | `voseo_emojis` | |
| 0.5 | ¿Cuántos mensajes te llegan por semana, más o menos, y por qué canal? | Menos de 3000 por mes (límite del plan básico) | |

## 1. Canales (Atención)
| # | Pregunta | Supuesto (sin confirmar) | Respuesta |
| --- | --- | --- | --- |
| 1.1 ★ | ¿Por dónde te escriben las clientas: WhatsApp, Instagram, los dos? ¿Cuál es el principal? | WhatsApp e Instagram | |
| 1.2 ★ | ¿Tu WhatsApp es común, WhatsApp Business o no tenés? ¿El número se puede dedicar a Raphael? | Hay que usar un número aparte o de prueba: la v1 va con cuentas que administra Damián (ver CONTEXT §6, Meta) | |
| 1.3 | ¿Tu Instagram es de empresa/creadora o personal? | Cuenta profesional | |
| 1.4 ★ | ¿Qué te gustaría que Raphael conteste solo y qué querés ver antes? | Contesta solo lo que está en el perfil; reclamos, dudas y precios fuera de lista van a ella | |
| 1.5 | ¿Qué preguntas te hacen todos los días? Anotá las 10 más repetidas. | Horarios, envíos, formas de pago, ubicación, si trabaja con tela propia | |
| 1.6 | ¿Hay clientas o temas con los que NO querés que el bot hable (reclamos, mayoristas, familiares)? | Reclamos siempre a ella | |

## 2. Encargos a medida (Encargos)
| # | Pregunta | Supuesto (sin confirmar) | Respuesta |
| --- | --- | --- | --- |
| 2.1 ★ | ¿Qué prendas hacés? Para cada una: precio base y cuántos días tarda. | vestido 150000/30 d, vestido de novia 450000/60 d, traje 220000/35 d (son los del piloto, no de ella) | |
| 2.2 | ¿Qué cosas suben el precio (largo, bordado, tela, urgencia)? ¿Cuánto? | largo +20 %, bordado +40000 (piloto) | |
| 2.3 ★ | ¿Qué datos necesitás de la clienta antes de pasar un presupuesto? | prenda, ocasión, fecha, detalles, referencias, medidas, nombre | |
| 2.4 | ¿Cuándo es "urgente"? ¿Cobrás extra? | menos de 15 días | |
| 2.5 | ¿Cómo tomás las medidas: en persona, por foto, con una cinta que te mandan? | En persona, en el turno | |
| 2.6 | ¿Qué estados tiene un encargo para vos (en confección, prueba, listo, entregado)? ¿Falta alguno? | en_confeccion, prueba, listo, entregado, cancelado | |
| 2.7 | ¿Cuándo querés que se le avise a la clienta que cambió el estado? | Pide tu OK cada vez (`avisar_estado`, regla general del 25 nov); se puede relajar por instalación solo si lo confirmás a mano | |
| 2.8 | ¿Aceptás cancelaciones? ¿Qué pasa con la seña? | Cancelar pide aprobación de ella | |

## 3. Cobros y señas (Cobros)
| # | Pregunta | Supuesto (sin confirmar) | Respuesta |
| --- | --- | --- | --- |
| 3.1 ★ | ¿Cobrás seña? ¿De cuánto? ¿Y el saldo cuándo? | 50 % de seña | |
| 3.2 ★ | ¿Cómo te pagan: transferencia, efectivo, Mercado Pago, tarjeta? ¿Pasás un alias? | transferencia y efectivo; alias y titular a completar | |
| 3.3 | ¿Cómo te enterás de que llegó una transferencia? ¿Te mandan comprobante? | La clienta avisa y ella confirma (`confirmar_pago` pide aprobación) | |
| 3.4 | ¿Hacés factura? ¿Sos monotributista? | Sin dato. No es de esta brigada: si hace falta, va a Legales (16) | |
| 3.5 | ¿Fiás o hacés cuotas? | No | |

## 4. Turnos y pruebas (Agenda)
| # | Pregunta | Supuesto (sin confirmar) | Respuesta |
| --- | --- | --- | --- |
| 4.1 ★ | ¿Qué días y horarios das turnos (toma de medidas, pruebas, retiro)? | jueves de 16 a 19, sábados de 10 a 13 (piloto) | |
| 4.2 | ¿Cuánto dura cada turno? ¿Cuántas pruebas hace falta por prenda? | Sin dato | |
| 4.3 | ¿Cuántos días antes querés recordarle el turno a la clienta? | 3 días | |
| 4.4 | ¿Querés confirmar vos cada turno o que Raphael lo confirme si el horario está libre? | Lo confirma ella (`confirmar_turno` pide aprobación) | |
| 4.5 | ¿Usás Google Calendar o una agenda de papel? | Papel o nada; el calendario lo lleva Raphael | |

## 5. Avisos y la app
| # | Pregunta | Supuesto (sin confirmar) | Respuesta |
| --- | --- | --- | --- |
| 5.1 ★ | ¿Qué celular usás? ¿Es Android? (la app 1.1.0 es solo Android) | Android | |
| 5.2 | ¿A qué hora te sirven los avisos? ¿Alguna franja en la que no quieras que te molesten? | Sin franja | |
| 5.3 | ¿Qué querés que te avise sí o sí (seña sin llegar, turno nuevo, reclamo, pedido urgente)? | Esos cuatro | |
| 5.4 | ¿Preferís recibir los avisos por la app o también por WhatsApp? | App | |

## 6. Tienda y catálogo
| # | Pregunta | Supuesto (sin confirmar) | Respuesta |
| --- | --- | --- | --- |
| 6.1 ★ | ¿Vendés online hoy? ¿Dónde: Tiendanube, Shopify, WooCommerce, Instagram, solo por mensaje? | Sin tienda web: `store.source.kind: none` | |
| 6.2 ★ | Si tenés tienda, ¿tenés acceso de administradora para sacar un token de solo lectura? | Sin dato | |
| 6.3 | ¿Tenés productos de stock (lo que se vende hecho) además de lo a medida? ¿Cuántos? | Sin dato; lo a medida no usa catálogo | |
| 6.4 | ¿Querés que Raphael le pase fotos o links de modelos a las clientas? ¿De dónde salen las fotos? | Solo con link de la tienda pública si existe | |
| 6.5 | ¿Querés que Raphael tome pedidos de la tienda o solo que conteste con lo que hay? | Solo lectura (v1) | |

## 7. Lo que no puede hacer solo (autonomía)
Preguntar cómo se sentiría con cada punto. Los niveles de hoy salen del manifiesto y lo irreversible no baja solo a automático.
| # | Pregunta | Supuesto (sin confirmar) | Respuesta |
| --- | --- | --- | --- |
| 7.1 ★ | ¿Te molesta aprobar cada presupuesto antes de que salga? | `enviar_presupuesto` en aprobación | |
| 7.2 | ¿Y cada confirmación de seña? | `confirmar_pago` en aprobación | |
| 7.3 | ¿Qué te daría tranquilidad: ver todo en un resumen diario, o aprobar mensaje por mensaje? | Aprobar caso por caso, con confianza progresiva (10 aprobaciones) | |

## 8. Expectativas y cierre
- ¿Qué tarea de tu día te gustaría sacarte primero de encima?
- ¿Qué te daría miedo que Raphael hiciera mal?
- ¿Cuánto estarías dispuesta a pagar por mes? (dato comercial para Damián; no se carga en el perfil)
- ¿Podemos usar tus conversaciones reales (sin datos de tus clientas) para probar? ¿Qué datos de tus clientas NO querés que se guarden? (Ley 25.326: verificar con fuente vigente antes de definir qué se guarda; es tema de Legales)

## 9. Revisión de alcance de Tienda (24 nov 2026)
Lo que hay: cocinero `tienda` de solo lectura con adaptador por feed JSON/CSV por URL y adaptadores de Tiendanube, Shopify y WooCommerce (agregados el 23 nov por pedido de Damián, sin probar contra tiendas reales). Comandos: `productos`, `catalogo`, `sincronizar`.

Lo que se recomienda, con supuestos marcados:
- **Supuesto A:** la clienta hace ropa a medida y probablemente vende por mensaje o Instagram, sin tienda web. Si es así, la v1 no necesita catálogo: dejar `kind: none` y no gastar tiempo en adaptadores. Se confirma con 6.1.
- **Supuesto B:** si tiene Tiendanube (la plataforma de uso más común en Argentina; dato no verificado), alcanza el adaptador existente con un token de solo lectura. Se confirma con 6.1 y 6.2, y la prueba real queda pendiente.
- **Alcance v1 que se mantiene:** solo lectura, nada de crear pedidos ni tocar stock. Lo a medida va por Encargos, no por Tienda.
- **Fuera de alcance por ahora:** tomar pagos online, sincronizar stock hacia afuera, imágenes subidas por Raphael.
- **Si no hay tienda:** la "tienda" se arma con los `prices` de Encargos (prendas base y recargos). Si ella quiere mostrar modelos, hace falta un feed JSON/CSV simple, y eso es decisión posterior a la entrevista.
- **Riesgo:** de los tres adaptadores de plataforma ninguno se probó contra una tienda real; no prometerlos hasta probarlos.

## 10. Ajustes a módulos según las respuestas (pendientes)
No se tocó código antes de tener respuestas: cualquier ajuste sería inventar. Cuando estén, revisar en este orden:
| Módulo | Qué puede cambiar | Depende de |
| --- | --- | --- |
| Atención | FAQ propias, tono, qué deriva a la dueña | 0.4, 1.4 a 1.6 |
| Encargos | prendas, recargos, pasos requeridos, estados | 2.1 a 2.8 |
| Cobros | % de seña, alias, medios de pago | 3.1 a 3.3 |
| Agenda | turnos, recordatorios, confirmación | 4.1 a 4.4 |
| Avisos | franjas y eventos | 5.2 a 5.4 |
| Tienda | kind del adaptador, URL pública | 6.1 a 6.5 |
| Autonomía | niveles por acción | 7.1 a 7.3 |
