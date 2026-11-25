# Registro · 03-servidor-app-instalador · Servidor, app e instalador

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## Pendiente para 03 (anotado por el mando, 24 nov 2026)
Decisión de Damián: Raphael personal pasa al modelo cliente-servidor, igual que Empresas. Un solo cerebro en la PC y todas las pantallas como clientes.
- La PC corre el servidor de Raphael personal como servicio de fondo: arranca con Windows y sigue andando con el panel cerrado.
- El panel de escritorio y la app de Android pasan a ser clientes de ese servidor (misma API que Empresas), con los mismos datos y la misma conversación.
- Objetivo: usar Raphael desde el celular mientras la PC esté prendida y con internet, aunque el panel esté cerrado.
- Acceso desde fuera de casa por una red privada (por ejemplo Tailscale), sin abrir puertos del router. Auth por token y las aprobaciones de siempre.
- Prioridad: después de entregar Empresas a la clienta. Referencia: el relay y la app con enlace al teléfono de JarvisRemote, en `3-mando/c-referencia/servidor-app-installer/`.

## 2026-11-24 · Adopción de la API y el kit del VPS
Resumen de cierre:
- Se adoptaron `servidor/api` y `c-despliegue/vps`: 26 tests y ruff en verde; las rutas del armado ya coincidían con el árbol a/b/c.
- Probado en la nube: `armar_paquete.py` (110 archivos, sin `.env`, bases ni claves), `instalar-v2.sh` en modo "solo archivos", arranque de la API, `/api/v1/health` y verificación del webhook; `bash -n` de los scripts.
- Se corrigieron rutas viejas (`nucleo\`, `obra\`) en `requirements-vps.txt` y los LEEME, y se agregó el checklist previo al montaje y `NVIDIA_API_KEY` (comentada) a `meta.env.plantilla`.
- Sin credenciales reales. Falta: VPS real (systemd, Caddy, DuckDNS), Meta real, copia fuera del servidor y alertas.

## 2026-11-25 · Un solo arranque y un solo archivo de claves
Resumen de cierre:
- `raphael_empresas_api/entorno.py`: lee `raphael.env` (también `meta.env` y `tienda.env`) sin pisar el entorno del sistema y arma el chequeo de arranque (IA, Meta, tienda, perfil, clave de la app) sin mostrar ningún valor. `python -m raphael_empresas_api chequear [--real]` y `servir` lo imprimen.
- `c-despliegue/windows/arrancar.bat`, `raphael.env.plantilla` y `QUE-CARGAR.md` (el único documento de claves).
- 7 tests nuevos (33 en el servidor, puerta 831). Probado en la nube con webhook mock y OpenRouter falso. Sin probar: el .bat en Windows, el túnel, OpenRouter y Meta reales.
- Pendiente: perfil real de la clienta (entrevista); decidir si las respuestas a clientes pueden usar IA (hoy solo reglas).

## 2026-11-25 · Configuración desde la app
Resumen de cierre:
- Raphael arranca sin claves. La clave de la app se genera sola la primera vez (se muestra una vez y queda en `clave-inicial.txt`); el chequeo ya no la marca como faltante.
- Pantalla de Configuración web (`/config`) y API `/api/v1/config`: poner o sacar OpenRouter, Meta (modo mock/real, WhatsApp, Instagram), URL pública y tienda; se guardan solo en `raphael.env` local, se aplican en caliente y nunca se devuelven completas.
- Tests: server 42, core 409, puerta 841. Pendiente: lo mismo en la app Android; `/config` no pasa por Caddy en el VPS (hay que habilitarlo ahí si se quiere).

## 2026-11-25 · Raphael personal cliente-servidor y lienzo en blanco
Resumen de cierre:
- Nuevo `raphael_personal_api` (boot, cerebro, app, página web, `python -m raphael_personal_api servir|chequear|clave`): servidor de Raphael personal sobre el orquestador maestro. Charla, pendientes (nada se aprueba solo; lo `humano` solo se resuelve), estado del cerebro, brigadas, configuración en caliente y voz (`/api/v1/voz*`, con el `speech_from` del orquestador si está instalado). Brigadas de la instalación que aún no existen: "no instaladas", no rompen.
- Cerebro mixto: `c-despliegue/personal/modelos.personal.yaml` (local = Ollama/LM Studio, gratis = NVIDIA, pago apagado). Lo privado (Seguridad, Investigación, Memoria, Operaciones) solo admite proveedores de localhost; con el local apagado va por reglas, avisa una vez por cambio y nada sale a la nube (test con transporte falso). Roles cambiables con `RAPHAEL_ROL_*`, `RAPHAEL_PRIVADAS`, `OLLAMA_*`, `LMSTUDIO_*`, `LOCAL_LLM_*`; una combinación que abra lo privado a la nube se rechaza.
- Windows: `instalar-personal.bat`, `instalar-servicio.bat` (tarea al iniciar sesión, sin ventana), `arrancar-personal.bat`, `celular-tailscale.bat` (tailscale serve, no Funnel). Arreglado el test que fallaba en Windows: `permisos.py` restringe `raphael.env` y `clave-inicial.txt` con `icacls` (en Linux, 600).
- Empresas: `/webhook/mercadopago` (responde al toque y pasa `mp_aviso` a la brigada Cobros; nunca confirma), variables `MP_*`, `TRANSFER_*`, `LOCAL_LLM_*`, `DUCKDNS_*`, `HCLOUD_TOKEN` en `/config` y en el chequeo, y `puentes.py`: acepta `MP_*` y `MERCADOPAGO_*` (las piezas 4 y 15 los nombraron distinto) y vuelca `TRANSFER_*`/`MP_MODE` a una copia efectiva de la instalación (`installation.efectiva.yaml`).
- Tests: server 88 (eran 51). **No probado:** Windows (los .bat, la tarea, `icacls`, Tailscale), Ollama/LM Studio/NVIDIA reales, voz real, Mercado Pago real; el webhook se probó contra un comando simulado porque `mp_aviso` llega con el PR 14.
- Eventos para otras piezas: login fallido publica `acceso.fallido {source, device, locked}` (Seguridad, sin la clave probada); API personal `POST /api/v1/command` y `GET /api/v1/events?event=` para clientes como el globo de Geolocalización (`pines`, `capa`, `pin.agregado`).
- Pendiente: la app Android y el panel de escritorio como clientes de esta API (hoy los cubre la página web); activar/apagar brigadas desde la API; el `instalar` del VPS no incluye todavía `/webhook/mercadopago` en Caddy (revisar al montar).
