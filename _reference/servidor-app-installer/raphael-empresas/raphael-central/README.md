# raphael-central — licencias y soporte (lo maneja Damián)

| | |
|---|---|
| **Licencias** | Una clave por cliente (`RAPH-XXXX-XXXX-XXXX`) con plan y vencimiento. La primera instalación que la valida queda atada a ella. Se puede suspender, reactivar, cambiar de plan o liberar (si el cliente cambia de equipo) |
| **Latidos** | Cada instalación avisa cada 15 min: versiones, uso del mes, costo de IA, pendientes, envíos fallidos. Sin datos de clientes |
| **Panel** (`/admin`) | Todas las instalaciones con alertas: sin latido hace más de 1 hora, envíos fallidos, tope de mensajes superado, licencia por vencer |

## Desplegar

```bash
docker build -t raphael-central .
docker run -d --restart unless-stopped -p 8070:8070 -v $PWD/datos:/datos \
  -e CENTRAL_ADMIN_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')" raphael-central
```

Con HTTPS adelante. Guardá el `CENTRAL_ADMIN_TOKEN`: es la clave del panel `/admin`.

Crear una licencia sin abrir el panel:

```bash
docker exec -it <contenedor> python -m raphael_central licencia --cliente "Taller X" --plan pro --vence 2027-01-01
```

## Desarrollo

```bash
python -m pytest -q
```
