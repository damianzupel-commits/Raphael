# raphael-servidor — Raphael en el equipo del cliente

Corre en el mini PC de cada empresa. Junta el harness con todas las brigadas y le agrega:

| | |
|---|---|
| **Panel de la dueña** (`/panel/`) | App web instalable en el celular: pendientes para aprobar, conversaciones, encargos, agenda, dudas, probador y estado |
| **WhatsApp e Instagram** | Webhook de Meta (`/webhook/meta`, con firma verificada) o cola del relay; respuestas por la API de Meta |
| **Licencia** | Valida contra el central cada 6 h; si el central no responde, sigue 7 días. Vencida: guarda los mensajes pero no responde |
| **Latido** | Cada 15 min manda al central versiones, uso y avisos. Nunca conversaciones ni datos de clientes |
| **Backups** | Diarios, cifrados con `RAPHAEL_CLAVE_BACKUP`, se conservan 30 |
| **Tareas** | Recordatorios de agenda (`tick`) cada 15 min |
| **Tienda de brigadas** | El cliente arranca con el orquestador; desde el panel descarga y activa brigadas del catálogo (`catalogo.yaml`) y se acoplan al harness sin reiniciar |
| **Seguridad** | Clave de la dueña con scrypt, sesiones firmadas, bloqueo tras 5 intentos fallidos |

## Instalar en un mini PC (Linux)

```bash
mkdir raphael && cd raphael
for r in harness orquestador atencion encargos cobros agenda avisos servidor; do
  git clone https://github.com/damianzupel-commits/raphael-$r.git
done
raphael-servidor/despliegue/instalar.sh perfil-del-cliente.yaml   # 1ª vez: crea datos/.env y pide la licencia
nano datos/.env                                                   # completar relay, central y WhatsApp
raphael-servidor/despliegue/instalar.sh perfil-del-cliente.yaml   # 2ª vez: construye, pide la clave del panel y arranca
```

La imagen corre **todos los tests** al construirse: si uno falla, no se instala.
Actualizar: `raphael-servidor/despliegue/actualizar.sh` (si fallan los tests, vuelve a la versión anterior).

## Desarrollo

```bash
# con los repos raphael-* lado a lado
mkdir -p /tmp/datos && cp ../raphael-harness/ejemplos/perfil-ropa-medida.yaml /tmp/datos/perfil.yaml
PYTHONPATH=src:../raphael-harness/src RAPHAEL_DIR=/tmp/datos RAPHAEL_DEV=.. python -m raphael_servidor correr --puerto 8080
# abrir http://localhost:8080 → elegir clave → pestaña Probador
python -m pytest -q
```

## Conectar WhatsApp e Instagram (modo real)

1. App de Meta con WhatsApp y/o Instagram (requiere App Review para producción).
2. Webhook de la app → URL del **relay** (`https://relay…/webhook/meta`) con el `META_VERIFY_TOKEN` del relay.
3. En el relay, agregar la instalación a `instalaciones.yaml` (id de `datos/servidor.json`, token, phone_number_id).
4. En `datos/.env`: `RAPHAEL_MODO=real`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `INSTAGRAM_TOKEN`, `RAPHAEL_RELAY_URL`, `RAPHAEL_RELAY_TOKEN`.
5. Fuera de la ventana de 24 h WhatsApp solo acepta plantillas aprobadas: esos envíos quedan en
   "envíos fallidos" (panel → Estado) para que la dueña los mande a mano.

## Restaurar un backup

```bash
docker compose exec raphael python -m raphael_servidor restaurar /datos/backups/raphael-AAAAMMDD-HHMMSS.sqlite.cifrado
docker compose restart
```
