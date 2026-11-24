# raphael-relay — los mensajes de Meta, del internet al local

Los mini PC de los clientes están detrás del router del local, sin IP pública, y Meta necesita
una URL pública para mandar los mensajes. El relay es esa URL:

```
Meta ──webhook──► relay (nube) ──cola por instalación──► mini PC del cliente (retira cada 3 s)
                                                          └──respuestas──► API de Meta (directo)
```

- Verifica la firma de Meta (`X-Hub-Signature-256`) y separa cada webhook por cliente
  (`phone_number_id` de WhatsApp, id de la cuenta de Instagram).
- Cada equipo retira **solo lo suyo** con su token (`GET /cola`, `POST /cola/ack`).
- Guarda los mensajes solo hasta que se retiran (máximo 7 días). Las respuestas no pasan por acá.
- Uno solo para todos los clientes; no necesita base de datos externa.

## Desplegar (VPS o Render, con HTTPS)

```bash
cp instalaciones.ejemplo.yaml datos/instalaciones.yaml     # una entrada por cliente
docker build -t raphael-relay .
docker run -d --restart unless-stopped -p 8090:8090 -v $PWD/datos:/datos \
  -e META_APP_SECRET=... -e META_VERIFY_TOKEN=... raphael-relay
```

Poner un proxy con HTTPS adelante (Caddy, Cloudflare o el de Render) y configurar en la app de
Meta el webhook `https://relay.tudominio.com/webhook/meta`.

## Desarrollo

```bash
python -m pytest -q
```
