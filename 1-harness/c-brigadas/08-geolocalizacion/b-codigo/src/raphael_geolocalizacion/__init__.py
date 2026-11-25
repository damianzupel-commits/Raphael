"""Brigada Geolocalización pública de Raphael (harness v2): OSINT de infraestructura con fuentes públicas.

Cocineros: `ip-infra` (IPs, dominios y Shodan), `cripto` (direcciones BTC y ETH) y `capas` (capas del globo, barcos y
los pines guardados). Todo lo que declara (acciones con su nivel, eventos, comandos) está en `manifest.yaml`, la única
fuente de verdad. Solo importa `raphael_core` y la stdlib: ninguna otra brigada.

Las fuentes son enchufables: `FuentesReales` (internet) y `FuentesSimuladas` (datos fijos, sin red, para los tests y para
probar el globo sin claves). Ver `fuentes/`.
"""

__version__ = "1.0.0"
