# Raphael Empresas en Oracle Cloud (gratis)

Todo lo que hay que hacer para que la clienta abra la app y ande, sin PC. Son unos 30–40 minutos la primera vez.

## 1. Crear la cuenta y el servidor
1. Entrá a **cloud.oracle.com** → *Sign up*. Pide una tarjeta solo para verificar tu identidad (retienen un monto chico y lo devuelven).
   Elegí como **región de origen** una cercana (por ejemplo *Brazil East (Sao Paulo)*). No se puede cambiar después.
2. Menú → *Compute* → *Instances* → **Create instance**.
   - Imagen: **Canonical Ubuntu 24.04** (o 22.04).
   - Forma: la gratis. Si hay cupo, *Ampere (ARM) A1* con 1 CPU y 6 GB; si dice "Out of capacity", elegí la **VM.Standard.E2.1.Micro (AMD, 1 GB)**. Con cualquiera de las dos alcanza.
   - *Add SSH keys* → **Generate a key pair** y **descargá la clave privada** (`.key`). Guardala: sin ella no podés entrar.
3. Cuando esté *Running*, copiá su **IP pública**.

## 2. Un dominio gratis
1. En **duckdns.org** entrá con Google o GitHub y creá un nombre, por ejemplo `minegocio` → `minegocio.duckdns.org`.
2. En *current ip* pegá la IP pública de Oracle y tocá *update ip*.

## 3. Subir Raphael al servidor (desde tu PC, en PowerShell)
```
scp -i RUTA\clave.key raphael-nube.tgz ubuntu@IP-PUBLICA:~
ssh -i RUTA\clave.key ubuntu@IP-PUBLICA
```
Ya adentro del servidor:
```
tar xzf raphael-nube.tgz
cd raphael-nube
sudo ./instalar-nube.sh minegocio.duckdns.org
```
Te pide que elijas la **clave del panel** (la de la dueña). Al final te muestra la IP y los pasos que faltan.

## 4. Abrir los puertos 80 y 443 en Oracle (obligatorio)
En la consola de Oracle: *Instancia* → *Virtual cloud network* → *Security Lists* → la lista por defecto → **Add Ingress Rules**:
- Source CIDR `0.0.0.0/0`, protocolo TCP, puerto destino **80**.
- Lo mismo con el puerto **443**.

(El firewall interno del servidor ya lo abre el script.)

## 5. Probar
Abrí **https://minegocio.duckdns.org/panel/** en cualquier navegador. El certificado HTTPS tarda un minuto la primera vez.
Entrá con tu clave → Estado → **Inteligencia artificial** y cargá la clave de NVIDIA (u otra de la nube).

## Mantenimiento
- Ver si anda: `systemctl status raphael` · logs: `journalctl -u raphael -n 100`
- Actualizar: subí el `raphael-nube` nuevo y corré `sudo ./actualizar-nube.sh` (hace backup y vuelve atrás solo si falla).
- **Backups**: se guardan cada día en `/opt/raphael/datos/backups`, cifrados con `RAPHAEL_CLAVE_BACKUP` (está en `/opt/raphael/datos/.env`; copiala a un lugar seguro). Bajá los backups a tu PC de vez en cuando:
  `scp -i RUTA\clave.key "ubuntu@IP:/opt/raphael/datos/backups/*" .`
- Oracle puede reclamar servidores gratis que están totalmente inactivos. Con Raphael andando no suele pasar; igual no dependas de un único backup.

## La app del celular
Se compila con la dirección ya adentro, así la clienta solo instala, abre y pone su clave:
```
cd raphael-android
./gradlew assembleRelease -Pservidor=https://minegocio.duckdns.org
```
Para que WhatsApp e Instagram le escriban a Raphael hay que pasar la revisión de Meta; hasta entonces queda en modo prueba (`RAPHAEL_MODO=mock` en `/opt/raphael/datos/.env`).
