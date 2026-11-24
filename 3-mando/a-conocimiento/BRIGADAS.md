# Brigadas de Raphael (al 21 nov 2026)

Fuente: INVENTARIO-FASE0.md y el código de JarvisRemote (backend/app/mission_control.py). Lo marcado "no construida" viene del spec.

## 1. Raphael personal (JarvisRemote): 10 brigadas del Centro de Mando
1. Seguridad: auditoría y pentest (modos ataque y defensa). El pentest activo corre solo en tu PC.
2. Antimalware: protección activa (YARA, ClamAV).
3. Investigación: forense. Ayudantes conocidos: Scout y Forense.
4. Geolocalización pública: mapa y OSINT.
5. Memoria · Cerebro: consolidación. Última validación 4/4 (16/11).
6. Ingesta: conocimiento.
7. Trading: mercados.
8. Operaciones: PC y celular.
9. Autorreparación: auto-mejora.
10. Contenido: imagen y video (marcada "futura" en el Centro de Mando). La base es la brigada de Video del motor (ffmpeg, Whisper, tools video_*, Instagram pendiente de aprobación), que es la que se estaba armando.

Declaradas en el motor genérico (brigades\registry.py): cerebro, investigacion, seguridad, video; scout como legado. Más las que se creen por borrador con tu OK.

## 2. Raphael Empresas: 5 brigadas construidas
1. Atención: WhatsApp e Instagram, reclamos.
2. Agenda: turnos y recordatorios.
3. Cobros: cobros y deudas.
4. Encargos: pedidos a medida.
5. Avisos: alertas al dueño.
No son brigadas, son soporte: orquestador (ruteo y secretaria), harness, servidor, relay, central, android.

## 3. Empresas dentro de Raphael personal: brigada 11
**11. Empresas** (una sola brigada, con su jefe). Sus módulos entran como cocineros (agentes permanentes):
- Atención, Agenda, Cobros, Encargos, Avisos
- Secretaria (del orquestador de Empresas)
- Tienda (nuevo, conector agnóstico)
La jefa de la brigada es la Secretaria (raphael-orquestador). En el harness de Empresas ese mismo rol es el orquestador.
Raphael Empresas queda intacto y se envuelve con adaptadores.

Nota de vocabulario: en el código de JarvisRemote "ayudante" es efímero (nace y muere por tarea). Los módulos de Empresas son permanentes, así que son cocineros.

## 4. Familia Raphael (spec, no construidas salvo lo reutilizado)
- Gestión: "Gestión del negocio" (es la brigada 11 de arriba).
- Seguridad: "Defensa y auditoría" (pasiva: auditor de código, antimalware, forense, vigilancia defensiva). Sin pentest.
- Innovación: "Investigación y conocimiento" (Scout, Cerebro, ideas y prototipos, vigilancia de tendencias).
- Marketer: "Contenido y campañas" (contenido, Instagram, video, campañas, analítica).
- Legales: "Documentos y cumplimiento" (documentos, cumplimiento, riesgos, archivo). Brigada nueva.

## Totales
Personal 10 + Empresas adentro 1 = 11. Empresas solo: 5. Familia: 5 brigadas, de las cuales 1 ya existe (Gestión) y 3 reutilizan código de JarvisRemote.

## Sin verificar
- Los ayudantes de cada brigada personal (solo se conocen los de Investigación).
- Las brigadas del Raphael viejo con la bolita flotante (no ubicado).
