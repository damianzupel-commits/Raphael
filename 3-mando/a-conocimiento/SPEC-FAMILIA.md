# Spec: Familia Raphael (orquestador + 5 Raphaels)

19 nov 2026 · Damián

> Copia en Markdown del doc https://claude.ai/artifact/EamzfzFu2ZEgrmT98jDyzU (rev 26). Si hay diferencias, manda el doc.

## 1. Objetivo y principios

Construir la Familia Raphael: un orquestador con una IA de frontera dirige cinco Raphaels especializados (Gestión, Seguridad, Innovación, Marketer y Legales), cada uno con sus brigadas, y cada pieza se monta o se desmonta sin romper al resto.

**Vocabulario (de Damián, se respeta en código y UI):**

- **Raphael:** una vertical completa (por ejemplo Raphael Marketer).
- **Brigada:** un equipo dentro de un Raphael, declarado como dato (brigade spec).
- **Jefe de brigada:** coordina; nunca responde directo, delega, junta y sintetiza.
- **Cocinero:** agente permanente de una brigada; cada capacidad de negocio es un cocinero.
- **Efímero:** ayudante que nace para una tarea y muere al terminarla.
- **Orquestador:** el mando; recibe el pedido, reparte entre Raphaels y concluye.
- **Harness:** el núcleo común donde viven contrato, bus de eventos, almacén, políticas y modelos.

**Principios rectores (no negociables):**

1. **Modularidad total.** Cada brigada y cada Raphael funciona solo y, además, todos pueden trabajar juntos bajo el orquestador.
2. **Nadie se habla directo.** Ningún Raphael ni brigada importa ni llama a otro; todo pasa por el orquestador a través del harness.
3. **Montar y desmontar sin romper.** Sacar o agregar un Raphael es cambiar una línea de configuración; el resto sigue funcionando y los tests lo prueban.
4. **Portar, no tirar (Harness v2).** Lo que ya anda (Raphael Empresas y las brigadas de JarvisRemote) se porta a un harness único que unifica los dos motores. Se conserva el comportamiento probado y sus tests; el código original queda congelado como referencia hasta que cada pieza portada pase su regresión.
5. **Lo que sale al mundo o gasta plata pide aprobación** por defecto; el nivel es configurable.
6. **Todo falla con gracia.** Sin modelo o sin red, cada pieza cae a reglas y avisa; nunca inventa.
7. **Ningún secreto en el repositorio.** Claves y tokens viven en archivos de entorno cifrados o fuera del repo.

## 2. Decisiones cerradas

Estas decisiones las tomó Damián el 19 de noviembre de 2026; el constructor no las reabre.

| Tema | Decisión |
| --- | --- |
| Quién lo usa | Damián y, como producto, clientes que eligen qué Raphaels contratan (catálogo modular) |
| Dónde corre | Todo en un VPS (Hetzner, Ubuntu 24.04, unos 8 GB de RAM); sin modelos locales, todo por API |
| Cerebro del orquestador | Escalonado por plan: básico con Nemotron, pro con un modelo medio de Claude, premium y privado con el más potente; jefes con modelo medio; cocineros y efímeros con modelo barato; todo en modelos.yaml, un único punto de cambio |
| Alcance de la v1 | Los 5 Raphaels completos, construidos por fases con puertas de control |
| Reparto de brigadas | Aprobado tal cual (secciones 5 a 9); nombres: Raphael Gestión, Raphael Seguridad, Raphael Innovación, Raphael Marketer y Raphael Legales |
| Seguridad | Solo defensiva y pasiva desde la nube; el pentest activo queda fuera de la v1 y se corre en la PC de Damián |
| Autonomía | Configurable por Raphael y por cliente, con el nivel estricto como punto de partida y sin pisos fijos: el cliente puede dejar cualquier acción en automático |
| Datos | Una instalación por cliente; lo de Damián va en una instalación aparte |
| Interfaz | Una app, una pestaña por Raphael; el cliente ve solo lo que contrató |
| Comunicación | Los Raphaels se hablan solo a través del orquestador |
| Código existente | Harness v2: se portan y unifican los dos motores (decidido 21 nov). Empresas original queda congelado y sube al VPS tal cual para la primera clienta, en carril paralelo |
| Secretaria | En Raphael personal es jefa de la brigada Empresas: sin voz propia, reporta todo al orquestador maestro (decidido 21 nov) |
| Trading | Toda ejecución, demo o real, requiere aprobación de Damián (decidido 21 nov) |
| Proveedor de IA | Sin decidir; el harness lo deja configurable por rol y por plan (21 nov) |
| Idioma del código | Nombres de funciones, variables y clases en inglés; documentación, comentarios de alto nivel y mensajes al usuario en español rioplatense (21 nov) |
| Primera salida (clienta) | Los cinco módulos de Empresas juntos, como están hoy (21 nov) |
| Legales | Argentina primero, con aviso de que no reemplaza a un abogado |
| Memoria | Cada Raphael con la suya; el orquestador ve un resumen; desmontar un Raphael se lleva su memoria |
| Repos | Un repo por pieza en la cuenta damianzupel-commits, privados; Damián hace los push |

## 3. Arquitectura

[Diagrama: arquitectura · orquestador, harness y 5 Raphaels. Está en el doc.]

El orquestador es el único punto de entrada; los Raphaels se cargan en el harness y no se conocen entre sí.

**Capas.**

1. **Harness.** Núcleo común, reutilizado de Empresas (`raphael-harness` 0.4 o superior): contrato versionado, bus de eventos, almacén SQLite con un espacio por módulo, Policy Engine, pasarela de modelos y registro de módulos.
2. **Núcleo de la familia** (`raphael-familia-core`, nuevo): cargador de manifiestos, perfil, aislamiento de fallos y suite de contrato. Depende del harness y no lo modifica.
3. **Raphael.** Paquete propio con manifiesto, una o más brigadas y su espacio de memoria.
4. **Brigada.** Un dato (brigade spec) que ejecuta el motor genérico de jefe: modelo, cocineros, herramientas permitidas, qué se espera de la ejecución y su validación.
5. **Cocinero y efímero.** Agente permanente y ayudante por tarea.

**Manifiesto de cada Raphael** (`manifiesto.yaml`): id, nombre, versión, versión de contrato que exige, brigadas y cocineros, herramientas que aporta, permisos con su nivel de aprobación por acción, eventos que publica y consume, espacio de almacén, esquema de configuración, healthcheck, y qué exporta y qué borra al desmontarse.

**Montar y desmontar.**

- `perfil.yaml` lista los Raphaels activos; el cargador valida cada manifiesto contra el contrato antes de montarlo.
- Un Raphael que no valida o que falla queda marcado como caído y el resto sigue.
- Desmontar quita sus herramientas, rutas y pestaña, y ofrece exportar o conservar su memoria; no deja huérfanos en el bus ni en el almacén de otros.
- Reglas duras: ningún import entre Raphaels ni entre brigadas (un test lo verifica); todo intercambio va por eventos y contratos del harness; el contrato usa versionado semántico y es compatible hacia atrás.

## 4. Orquestador

El orquestador es el único que habla con el usuario y con los Raphaels; no ejecuta herramientas de dominio, reparte y concluye.

**Roles de modelo.** Cada rol se resuelve desde un archivo `modelos.yaml` por plan (básico, pro, privado, premium), que es el único punto de cambio:

| Rol | Qué hace | Nivel de modelo |
| --- | --- | --- |
| `mando` | Reparte el pedido entre Raphaels y concluye sobre sus reportes | IA de frontera (configurable por plan) |
| `voz` | Redacta la respuesta final al usuario, con verificador de fidelidad y plantilla de respaldo | Alto |
| `ruteo` | Clasifica el pedido y elige Raphaels | Bajo costo |
| `jefe` | Coordina una brigada: planifica, delega, sintetiza | Medio |
| `cocinero` | Agente permanente de una brigada | Según la tarea |
| `efimero` | Ayudante por tarea | Bajo costo |

**Flujo de un pedido.**

1. Llega por la app, WhatsApp o Instagram y se normaliza a un evento del harness.
2. `ruteo` decide a qué Raphaels corresponde; si es charla corta o una pregunta sobre Raphael mismo, contesta directo desde el registro de módulos.
3. `mando` propone el reparto; **código** lo valida (sin ciclos, dependencias declaradas) y lo ejecuta por niveles, en paralelo cuando no hay dependencia. El contexto de otro Raphael llega al jefe separado del pedido.
4. Cada jefe delega en sus cocineros o efímeros y devuelve un reporte estructurado.
5. Código junta los reportes; `mando` concluye; `voz` redacta una sola respuesta.
6. Todo queda en la auditoría.

**Reglas.**

- El jefe de brigada nunca responde directo: coordina, junta y explica.
- Las acciones de lectura corren de inmediato; las de escritura se proponen con ids reales y se ejecutan solo tras un "sí" explícito (cualquier otra frase cancela). Se rechazan ids o acciones inventadas por el modelo.
- Sin modelo o sin red, cae a reglas deterministas y avisa que lo hace.
- Tope de uso por plan; si se agota, el orquestador lo dice y no gasta más.
- Si un Raphael está desmontado o caído, el orquestador lo explica y sigue con los demás.
- Vista del dueño: aprobar, rechazar, resolver y ordenar solo existen dentro del contexto del dueño; cada orden queda auditada.
- Secretaria: lista tareas pendientes, recomienda y ejecuta lo que el dueño pida, hablando normal.
- Bucles proactivos (open loops): el orquestador puede revisar pendientes por su cuenta y avisar, sin ejecutar nada que requiera aprobación.

## 5. Raphael Gestión

Gestión es todo Raphael Empresas, envuelto sin tocarlo. Es la vertical que atiende clientes, agenda, cobra y organiza encargos para pymes; su primera usuaria es la clienta de ropa a medida.

**Brigada única: Gestión del negocio.** Cada capacidad de Empresas es un cocinero:

| Cocinero | Se reutiliza de | Qué hace |
| --- | --- | --- |
| Atención | `raphael-atencion` | Responde WhatsApp e Instagram (mensajes directos), maneja reclamos y conversaciones abiertas; delega al dueño con contexto y opciones |
| Agenda | `raphael-agenda` | Turnos, citas y recordatorios |
| Cobros | `raphael-cobros` | Seguimiento de cobros y deudas |
| Encargos | `raphael-encargos` | Pedidos a medida, estados y entregas |
| Avisos | `raphael-avisos` | Alertas y notificaciones al dueño (push del celular) |
| Secretaria | `raphael-orquestador` (agente) | Tareas pendientes, recomendaciones y ejecución por pedido del dueño |
| Tienda | Nuevo | Conector agnóstico a la tienda web de la clienta (ver abajo) |

**Cómo se envuelve.**

- El paquete `raphael-gestion` declara su manifiesto y registra los cocineros usando el contrato del harness de Empresas (`raphael-harness` 0.4 o superior). No copia ni edita el código de Empresas.
- Empresas sigue funcionando solo, con su servidor y su app, exactamente como hoy; los tests de sus repos deben seguir en verde sin cambios.
- Los conectores de Meta (`/webhook/meta`, firma, envío de texto) se reutilizan tal cual y se alimentan de las mismas credenciales por instalación.

**Cocinero Tienda (nuevo).** Se conecta a cualquier tienda sin importar la plataforma:

- Interfaz única de catálogo: productos, precios, stock, imágenes y pedidos.
- Adaptador por defecto: un feed de catálogo en JSON o CSV con una URL.
- Adaptadores opcionales: Tiendanube, Shopify y WooCommerce, cada uno detrás de la misma interfaz.
- Solo lectura de catálogo en la v1; cualquier acción de escritura en la tienda pide aprobación.
- Botón "Mi tienda" en la app que abre la tienda del cliente.

## 6. Raphael Seguridad

Seguridad es solo defensiva y pasiva en la nube. No existe ninguna herramienta de escaneo activo en el catálogo de la instalación en VPS, porque un escaneo desde la IP del servidor puede hacer que el proveedor lo suspenda.

**Brigada: Defensa y auditoría.**

| Cocinero | Se reutiliza de | Qué hace |
| --- | --- | --- |
| Auditor de código | Brigada de Seguridad y auditoría de JarvisRemote | Análisis estático de repos que el cliente autoriza: secretos expuestos, dependencias vulnerables, malas prácticas; solo lectura |
| Antimalware | Antímalware de JarvisRemote | Revisión pasiva de archivos y enlaces que el cliente sube (hashes, firmas, reputación por API) |
| Forense | Forense de JarvisRemote | Análisis de logs y artefactos entregados por el cliente; nunca toca sistemas ajenos |
| Vigilancia defensiva | Nuevo (sobre la salud del harness) | Monitorea la propia instalación: intentos de login, tokens por vencer, certificado, caída del servicio, backups; avisa al dueño |

**Reglas duras.**

- El modo `pasivo` es fijo en la instalación en VPS: las herramientas activas (nmap, ZAP, sqlmap y similares) no se cargan, no se pueden activar por configuración y hay un test que lo verifica.
- El pentest activo queda fuera de la v1. Si se retoma, corre en la PC de Damián, solo contra objetivos de una lista firmada por él y con aprobación por cada corrida.
- Todo hallazgo se reporta con severidad, evidencia y cómo corregirlo; nunca se explota nada.
- El auditor trabaja sobre copias de solo lectura de lo que el cliente autoriza; no guarda código ajeno más tiempo del necesario.

## 7. Raphael Innovación

Innovación investiga, recuerda y propone. Es el Raphael de conocimiento: lo consultan los demás a través del orquestador, nunca directo.

**Brigada: Investigación y conocimiento.**

| Cocinero | Se reutiliza de | Qué hace |
| --- | --- | --- |
| Investigación (Scout) | Raphael Scout de JarvisRemote | Búsqueda web trazable: cada afirmación con su fuente y fecha; distingue lo verificado de lo no verificado |
| Memoria y conocimiento (Cerebro) | Cerebro de JarvisRemote | Guarda y recupera notas en un vault propio de la instalación; un recuperador devuelve fragmentos con su origen |
| Ideas y prototipos | Nuevo | Genera y evalúa ideas, escribe specs y prototipos de código acotados, siempre en un espacio aislado sin tocar nada del cliente |
| Vigilancia de tendencias | Nuevo (sobre los bucles proactivos) | Sigue los temas que el cliente define y avisa cuando hay algo relevante, con resumen y fuentes |

**Reglas.**

- Nada se afirma sin fuente; si no hay, lo dice.
- Cerebro consolida notas sin mezclar temas no relacionados y no inventa; esas fallas ya aparecieron en las validaciones de JarvisRemote y el constructor debe reproducir esos casos como tests de regresión.
- Los embeddings corren por API o con un modelo liviano en el VPS; no hay modelos locales pesados.
- Cada instalación tiene su propio vault; desmontar Innovación permite exportarlo.

## 8. Raphael Marketer

Marketer crea contenido, edita video y publica en redes; nada sale al mundo sin la aprobación del dueño por defecto. Los mensajes directos los atiende Gestión, no Marketer.

**Brigada: Contenido y campañas.**

| Cocinero | Se reutiliza de | Qué hace |
| --- | --- | --- |
| Contenido | Nuevo | Copys, calendario editorial, guiones y carruseles, con el tono de la marca del cliente |
| Instagram | Brigada de Video de JarvisRemote (publicaciones pendientes de aprobación) | Prepara y publica historias, Reels y carruseles tras la aprobación del dueño |
| Video | Brigada de Video de JarvisRemote | Edición por pedido con ffmpeg y transcripción; carpeta fija y original intacto |
| Campañas y anuncios | Nuevo | Borradores de anuncios con presupuesto y segmentación; nada se activa ni gasta sin aprobación |
| Analítica | Nuevo | Métricas de las redes y recomendaciones de qué repetir |

**Instagram, requisitos de la plataforma.**

- La cuenta debe ser profesional (empresa o creador); las historias solo se pueden publicar desde cuentas de empresa.
- Se usa Instagram API con Instagram Login (no exige página de Facebook). Permiso de publicación: `instagram_business_content_publishing`.
- Para la v1 alcanza el acceso estándar, porque la app sirve a cuentas que Damián administra. Para que cualquier cliente conecte sus redes solo hace falta ser Tech Provider, con App Review y verificación de empresa de Meta; eso queda para una fase posterior.
- Publicar es un proceso de dos pasos (crear el contenedor y publicarlo) y Meta descarga el archivo desde una URL pública: el servidor expone medios con enlaces temporales firmados y los borra al terminar.
- Los tokens vencen: el cocinero los renueva antes del vencimiento y avisa si falla.

**Video en el VPS.**

- Un trabajo de video a la vez, con pocos hilos y prioridad baja, para no tumbar el servidor.
- Sin línea de tiempo visual: edición por instrucciones.
- La grabación de pantalla del Raphael personal queda fuera de la nube.

## 9. Raphael Legales (Argentina)

Legales prepara y revisa documentos y riesgos; no da asesoramiento legal ni reemplaza a un abogado. Todo lo que produce lleva ese aviso y nunca firma, envía ni presenta nada por su cuenta.

**Brigada: Documentos y cumplimiento.** Es una brigada nueva, sin código previo que reutilizar.

| Cocinero | Qué hace |
| --- | --- |
| Documentos | Borradores de términos y condiciones, política de privacidad, presupuestos, contratos de servicio y cartas, a partir de plantillas con variables del negocio |
| Cumplimiento | Checklist de cumplimiento para un pyme argentino: protección de datos personales, defensa del consumidor, facturación, y reglas de Meta y WhatsApp (consentimiento, plantillas, ventana de 24 horas) |
| Riesgos | Revisa textos, anuncios y publicaciones antes de salir y marca riesgos; Marketer y Gestión lo piden a través del orquestador |
| Archivo | Registro versionado de documentos emitidos y de consentimientos recibidos |

**Reglas.**

- Cada afirmación normativa cita su fuente oficial y la fecha en que se verificó; las normas cambian, así que se consulta la fuente en el momento y no se responde de memoria.
- Normas de partida a verificar con fuente vigente: Ley 25.326 de protección de datos personales, Ley 24.240 de defensa del consumidor y la normativa de facturación de ARCA (ex AFIP).
- Los borradores salen marcados como borrador y quedan en el archivo; el dueño decide si los usa.
- Jurisdicción configurable por instalación; la v1 trae solo Argentina.

## 10. Servidor, app e instalación por cliente

**Servidor.**

- VPS Hetzner con Ubuntu 24.04 y unos 8 GB de RAM (plan CX33 de referencia); `systemd` mantiene el servicio y Caddy da HTTPS automático con un dominio por instalación.
- Se parte de `raphael-servidor` 0.4 (FastAPI, login del panel, webhook de Meta, panel web) y se extiende con: lista de Raphaels montados, rutas por Raphael y pestañas armadas desde los manifiestos.
- Una instalación por cliente: usuario del sistema, carpeta, base de datos, claves y dominio propios. La instalación de Damián es otra y no comparte datos con ninguna de clientes.

**App.**

- Se parte de `raphael-android` (WebView nativo con la dirección del servidor fija, avisos por polling cada 15 minutos). El cliente solo la abre.
- Una pestaña por Raphael montado, más el chat con el orquestador; un Raphael no contratado no aparece.
- Ajustes: inteligencia artificial (proveedor y clave, nunca se devuelve la clave), autonomía por Raphael y conexión de redes y tienda.

**Instalador y mantenimiento.**

- `instalar-nube.sh` y `actualizar-nube.sh` se extienden para recibir el perfil de cliente (qué Raphaels montar) y arman la instalación completa; la actualización hace copia de seguridad y vuelve atrás sola si el servicio no queda sano.
- Copias de seguridad cifradas con copia fuera del servidor.
- Alerta al celular del dueño si el servidor cae o un token está por vencer.
- Instalación asistida para el primer cliente: Damián conecta las redes y la tienda junto a la clienta.

**Perfil por instalación.** Dos archivos describen todo:

- `perfil.yaml`: Raphaels y brigadas montados, identidad del negocio, jurisdicción.
- `modelos.yaml`: proveedor y modelo por rol, según el plan.

## 11. Autonomía, políticas y seguridad transversal

**Niveles de autonomía** (los del Policy Engine actual): `automatico`, `aprobacion` y `humano` (lo hace una persona). Cada acción de cada cocinero declara en su manifiesto su nivel por defecto.

| Tipo de acción | Nivel por defecto |
| --- | --- |
| Leer, analizar, resumir, preparar borradores | `automatico` |
| Publicar, enviar a terceros, responder a un cliente final | `aprobacion` |
| Cobrar, pagar, gastar presupuesto, activar anuncios | `aprobacion` |
| Borrar datos, firmar o presentar documentos, cambios irreversibles | `humano` |

El cliente puede cambiar el nivel por Raphael y por acción desde Ajustes; cada cambio queda auditado. Damián decidió que no hay pisos fijos: el cliente puede dejar cualquier acción en automático. Los valores de fábrica son los de la tabla, y subir a automático una acción con gasto o irreversible muestra una advertencia que hay que confirmar.

**Seguridad transversal.**

- **Contenido de terceros es dato, nunca instrucción.** Mensajes de clientes finales, páginas web, documentos y archivos subidos pueden intentar dar órdenes al modelo; el harness los marca como no confiables y ninguna acción de escritura se dispara solo por ellos.
- **Auditoría total.** Cada orden, aprobación, rechazo, acción y cambio de configuración se registra con quién, qué, cuándo y por qué.
- **Secretos.** Claves y tokens en el archivo de entorno de cada instalación, con cifrado de las copias de seguridad; nunca en el repositorio ni en los logs; la clave de IA nunca vuelve por la API.
- **Aislamiento.** Cada Raphael escribe solo en su espacio del almacén; un test intenta leer el espacio de otro y debe fallar.
- **Fallos aislados.** Un módulo que falla al montarse o en ejecución queda marcado como caído y no tumba al resto.
- **Tope de uso por plan** y registro del gasto en modelos.

## 12. Tests y criterios de aceptación

La v1 se acepta solo si todos estos tests pasan sin red y con modelos falsos inyectables. Cada repo corre sus tests y `ruff` en GitHub Actions en cada push.

| Test | Qué prueba | Criterio |
| --- | --- | --- |
| Contrato | Una suite compartida que todo Raphael y toda brigada debe pasar: manifiesto válido, versión de contrato compatible, healthcheck, desinstalación | Verde para los 5 Raphaels |
| Aislamiento de código | Un chequeo por análisis del código (AST) confirma que ningún módulo importa a otro módulo hermano | Cero imports cruzados |
| Matriz montar/desmontar | Arranca el harness con todos, con cada Raphael apagado, con uno solo y con ninguno, y corre el resto de la batería en cada caso | Verde en todas las combinaciones; el orquestador explica lo que falta |
| Aislamiento de datos | Un Raphael intenta leer el espacio de otro; desmontar uno no deja residuos ni afecta a los demás | Falla la lectura cruzada; export de datos funciona |
| Políticas | Ninguna acción de nivel `aprobacion` o `humano` se ejecuta sin confirmación; ids inventados se rechazan | Cero ejecuciones sin OK |
| Modo pasivo de Seguridad | Ninguna herramienta de escaneo activo se carga en la instalación en VPS | Catálogo sin herramientas activas |
| Degradación | Sin modelo o sin red, el orquestador responde por reglas y avisa | Sin errores no controlados |
| Regresión de Empresas | Los tests de los repos de Raphael Empresas corren sin modificarse | Todo verde, código de Empresas sin cambios |
| Regresión de Cerebro | Reproduce las fallas ya vistas: mezcla de notas no relacionadas e invención | No reaparecen |
| Humo en VPS | Instalación en máquina limpia, `/salud`, login, pestañas por Raphael, webhook en modo simulado | Todo responde |

**Fuera de los tests automáticos (los hace Damián):** probar con modelos reales, con una cuenta de Meta real y con la clienta.

## 13. Plan de construcción por fases

Se construye de corrido (decidido 21 nov), pero cada fase termina con una puerta automática (script con código de salida 2 si falla, no depende de que alguien la apruebe a mano): si sus tests no pasan, no se empieza la siguiente. Cada commit es chico y deja todo funcionando.

1. **Fase 0, preparación.** Inventariar el código de JarvisRemote (motor de brigadas, contratos, voz, turnos, tools) y los repos de Empresas; trabajar sobre copias; revisar que no haya claves ni archivos de entorno en el historial de git. *Puerta:* inventario escrito y los tests actuales de ambos mundos en verde.
2. **Fase 1, Harness v2.** Un solo núcleo que unifica el harness de Empresas (contrato, cargador, bus, almacén, políticas) y el motor de brigadas de JarvisRemote (BrigadeSpec, jefe, ayudantes, ruteo, config por rol). Incluye cargador de manifiestos, `perfil.yaml`, registro de módulos, políticas configurables sin pisos, modelos por rol, aislamiento de fallos, suite de contrato y matriz montar/desmontar, con un módulo de ejemplo. *Puerta:* los 21 tests del harness de Empresas portados y en verde, y el módulo de ejemplo se monta y se desmonta sin romper nada.
3. **Fase 2, orquestador.** Roles `mando`, `voz` y `ruteo`, reparto por DAG validado por código, modelos por plan, secretaria y confirmación de acciones. *Puerta:* flujo completo con modelo falso y degradación a reglas.
4. **Fase 3, Gestión.** Portar las piezas de Empresas al harness v2 (Secretaria, atención, agenda, cobros, encargos, avisos) y agregar el cocinero Tienda. *Puerta:* los tests de Empresas (111) portados y en verde, y matriz en verde con Gestión montado y desmontado.
5. **Fase 4, Innovación y Seguridad.** Scout, Cerebro, ideas y vigilancia de tendencias; auditor, antimalware, forense y vigilancia defensiva en modo pasivo. *Puerta:* regresión de Cerebro y test de modo pasivo.
6. **Fase 5, Marketer y Legales.** Contenido, Instagram, Video, campañas y analítica; documentos, cumplimiento, riesgos y archivo. *Puerta:* publicación solo con aprobación y aviso legal en toda salida de Legales.
7. **Fase 6, servidor, app e instalador.** Pestañas dinámicas, perfil por cliente, instalador y actualizador extendidos, copias de seguridad, alertas. *Puerta:* instalación limpia en un VPS con humo verde.
8. **Fase 7, endurecimiento.** Revisión de seguridad, README corto por módulo, tipos y `ruff` en todos los repos, CI por repo. *Puerta:* todos los criterios de la sección 12 en verde.

## 14. Pendientes y supuestos a verificar

Lo que no está decidido o no se verificó. El constructor no lo inventa: lo resuelve con el dueño o lo verifica leyendo el código.

| Tema | Estado |
| --- | --- |
| Rutas del motor de brigadas de JarvisRemote | No verificadas: el motor genérico, el esquema de brigada, los contratos, la voz y los turnos viven en el backend de JarvisRemote; el constructor debe inventariarlos en la fase 0 |
| Pisos de autonomía | Resuelto: Damián eligió sin pisos fijos, el cliente puede dejar cualquier acción en `automatico`. Subir a automático una acción con gasto o irreversible muestra una advertencia que hay que confirmar |
| Modelos por plan | Resuelto en lo general: orquestador escalonado (básico con Nemotron, pro con un modelo medio de Claude, premium y privado con el más potente), jefes con modelo medio, cocineros y efímeros con modelo barato. Falta fijar los modelos exactos de cada plan en modelos.yaml al construir |
| Video en el VPS | Con 8 GB de RAM y un trabajo a la vez debería alcanzar; si no, hay que subir de plan de servidor |
| Meta | La v1 conecta cuentas administradas por Damián; el flujo en que cada cliente conecta sus redes solo requiere ser Tech Provider, con verificación de empresa y App Review, y queda fuera de la v1 |
| Plantillas de WhatsApp | Fuera de la ventana de 24 horas hacen falta plantillas aprobadas; se definen cuando haya número real |
| Normativa argentina | Las normas citadas en Legales se verifican con fuente vigente al construir |
| Nombres | Resuelto: Raphael Gestión, Raphael Seguridad, Raphael Innovación, Raphael Marketer y Raphael Legales; no hay marca comercial aparte |
| Capacidad del VPS | Falta definir cuántas instalaciones de cliente caben en un mismo servidor |
| Raphael anterior con la bolita flotante | Ya está decidido archivarlo en `Documents\_Archivo`; la PC estaba desconectada y falta hacerlo |
| Repos de Damián | El `CLAUDE.md` de JarvisRemote dice que el repo es público y Damián indica que hoy es privado; hay que confirmarlo antes de pushear |
| Acceso del constructor | Necesita acceso de lectura a los repos de Empresas y a JarvisRemote, o copias de ambos |

## 15. Ejemplos y estructura de repos

Los ejemplos son ilustrativos: fijan la forma, y los nombres exactos los termina de definir el constructor.

**Estructura de repos.** Los repos actuales de Empresas y JarvisRemote no se editan. Donde el spec dice "se parte de" o "se extiende", se copia a un repo nuevo y se trabaja sobre la copia.

```text
raphael-familia-core/       cargador, manifiestos, perfil, suite de contrato, matriz de tests
raphael-familia-orquestador/ mando, voz, ruteo, reparto por DAG, secretaria
raphael-familia-servidor/   copia extendida de raphael-servidor: pestañas dinámicas, instalador
raphael-familia-android/    copia de raphael-android con dirección fija por instalación
raphael-gestion/            adaptadores de Empresas + cocinero Tienda
raphael-seguridad/          defensa y auditoría pasiva
raphael-innovacion/         Scout, Cerebro, ideas, tendencias
raphael-marketer/           contenido, Instagram, video, campañas, analítica
raphael-legales/            documentos, cumplimiento, riesgos, archivo
```

**Manifiesto de un Raphael** (`manifiesto.yaml`):

```yaml
id: gestion
nombre: Raphael Gestión
version: 1.0.0
contrato: 1            # el de Empresas; si el núcleo lo extiende, sube sin romper a Empresas
brigadas:
  - id: gestion-negocio
    cocineros:
      - {id: atencion, fuente: raphael-atencion}
      - {id: agenda, fuente: raphael-agenda}
      - {id: cobros, fuente: raphael-cobros}
      - {id: encargos, fuente: raphael-encargos}
      - {id: avisos, fuente: raphael-avisos}
      - {id: secretaria, fuente: raphael-orquestador}
      - {id: tienda, fuente: nuevo}
acciones:
  responder_cliente: {nivel: aprobacion}
  consultar_agenda:  {nivel: automatico}
  registrar_cobro:   {nivel: aprobacion}
eventos:
  publica: [mensaje.recibido, cobro.vencido]
  consume: [pedido.nuevo]
almacen: {espacio: gestion}
salud: {chequeo: raphael_gestion.salud:chequear}
desmontaje: {exporta: [datos], borra: [cache]}
```

**Perfil de una instalación** (`perfil.yaml`):

```yaml
cliente: clienta-ropa
dominio: ejemplo.duckdns.org
jurisdiccion: AR
plan: pro
raphaels:
  gestion:    {activo: true}
  marketer:   {activo: true}
  legales:    {activo: false}
  seguridad:  {activo: false}
  innovacion: {activo: false}
autonomia:
  gestion.responder_cliente: aprobacion
```

**Modelos por plan** (`modelos.yaml`; los modelos exactos se fijan al construir):

```yaml
planes:
  basico:
    mando:    {proveedor: nvidia, modelo: nemotron}
    jefe:     {proveedor: nvidia, modelo: nemotron}
    cocinero: {proveedor: nvidia, modelo: nemotron}
  pro:
    mando:    {proveedor: anthropic, modelo: <modelo-medio>}
    jefe:     {proveedor: anthropic, modelo: <modelo-medio>}
    cocinero: {proveedor: nvidia, modelo: nemotron}
  premium:
    mando:    {proveedor: anthropic, modelo: <modelo-mas-potente>}
    jefe:     {proveedor: anthropic, modelo: <modelo-medio>}
    cocinero: {proveedor: nvidia, modelo: nemotron}
```

## 16. Prompt para el constructor

Pegalo junto con este spec al empezar la sesión. (La versión actualizada, con reglas de seguridad de trabajo, está en `PROMPT-OPUS.md`.)

```markdown
Sos el constructor de la Familia Raphael. Leé el spec completo antes de escribir una línea y construí en el orden de la sección 13.

Reglas:
1. Trabajá sobre copias. Los repos de Raphael Empresas y JarvisRemote originales no se modifican.
2. No pases a la fase siguiente si los tests de la puerta de la fase actual no están en verde.
3. Commits chicos, uno por cambio, y cada uno deja todo funcionando.
4. Nada de secretos en el repo: claves y tokens van en archivos de entorno ignorados por git.
5. Ningún módulo importa a otro módulo hermano; todo pasa por el harness y el orquestador.
6. No inventes. Si falta un dato, elegí la opción más conservadora, márcala en el informe y seguí.
7. Interfaz, documentación y mensajes en español rioplatense.
8. Al cerrar cada fase entregá un informe corto: qué hiciste, qué tests pasan, qué decisiones tomaste y qué falta.
9. Si algo del spec se contradice con el código existente, gana el código que ya funciona; avisá la diferencia.

Empezá por la fase 0: inventario del código existente, revisión de secretos en el historial y línea base de tests.
```
