# Registro · 04-cuentas-y-apis · Cuentas y APIs

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 2026-11-25 · Catálogo, chequeo y verificación de cuentas
Resumen de cierre:
- Paquete `raphael_cuentas` (solo biblioteca estándar): catálogo único de 13 cuentas (OpenRouter, NVIDIA, modelo local, Meta webhook/WhatsApp/Instagram, Mercado Pago, transferencia, Tailscale, DuckDNS, Hetzner, tienda, broker pendiente), chequeo sin mostrar secretos, verificación real de solo lectura y simulada, y `.env.plantilla` y `ENTRADAS-LIENZO.md` generados desde el catálogo.
- 22 tests con adaptador simulado o abridor falso (sin red ni claves), ruff limpio. Nada probado contra cuentas reales: los endpoints de verificación y los nombres `MP_*`, `TRANSFER_*`, `LOCAL_LLM_*`, `DUCKDNS_*`, `HCLOUD_TOKEN` son supuestos a confirmar.
- Decisiones aplicadas: OpenRouter para Empresas, NVIDIA solo para lo no sensible de personal, modelo local para lo sensible, cobros por Mercado Pago más transferencia con confirmación manual, sin VPS por ahora (Tailscale Funnel), broker sin elegir. No se abrió ninguna cuenta.
- Pendiente para 15 (Empresas): leer `MP_*` y `TRANSFER_*` en el conector de cobros. Pendiente para 1/2 (harness y orquestador): poner el modelo local en el escalón `local` y no mandar lo sensible a la nube si está apagado. Pendiente para 3 (servidor): que `/config` y `chequear` lean las variables nuevas. Pendiente para 11 (Trading): su plantilla de broker.
- Pendiente para el coordinador: sumar la suite `cuentas` a `gate.py` (carpeta `2-entrega/c-despliegue/cuentas-y-apis/tests`, y la ruta a ruff), pasar `ENTRADAS-LIENZO.md` a `LIENZO-DAMIAN.md` y actualizar ESTADO.md.
