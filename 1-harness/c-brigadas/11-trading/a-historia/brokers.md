# Brokers para Trading (búsqueda del 25 nov 2026)

> **Decisión de Damián (25 nov): Interactive Brokers.** Adaptador hecho (`ibkr.py`, con versión simulada para los tests). Pasos en `ibkr-pasos.md`.

Pedido de Damián: 2 o 3 brokers con API que acepten residentes de Argentina, con cuenta demo y USD/JPY. **No se abrió ninguna cuenta.**
Lo verificado en la página oficial va marcado ✔; lo que sale de sitios comparadores (que cobran publicidad) va marcado ~ y hay que confirmarlo con el broker antes de abrir cuenta.

## Propuesta

### 1. Interactive Brokers (IBKR) — la más firme
- ✔ Argentina figura en su [lista oficial de países](https://www.interactivebrokers.com/en/accounts/open-account-country-list.php), sin nota de restricción.
- ✔ Cuenta demo (paper): se pide desde el portal de la cuenta real; la real no hace falta fondearla para usar la paper ([guía oficial](https://www.interactivebrokers.com/campus/trading-lessons/request-paper-trading-account/)). Datos de mercado en paper: solo con retraso hasta fondear.
- ~ API: TWS API (necesita TWS o IB Gateway abierto en la PC) y Client Portal Web API (REST). ~ Forex incluye USD/JPY (IDEALPRO). Confirmar que las órdenes de la paper entran por API (la guía oficial no lo dice explícito).
- Pros: regulada en Tier-1, cuenta de verdad aceptada acá, paper gratis, mucho material. Contras: hay que dejar TWS/Gateway corriendo en la PC y volver a iniciar sesión seguido; onboarding más largo; hay que escribir el adaptador (no existe todavía).

### 2. IG — la segunda opción
- ✔ API [REST + streaming (Lightstreamer)](https://www.ig.com/en/trading-platforms/trading-apis/how-to-use-ig-api), con endpoint demo; para sacar las credenciales de API hay que tener una cuenta real (la demo sola no alcanza).
- ~ Un comparador la lista como aceptando residentes de Argentina; la página oficial NO menciona Argentina: hay que preguntarle a IG. Opera CFDs (USD/JPY incluido, a confirmar).
- Pros: API sencilla (REST), demo clara. Contras: CFDs, límite de unos 40 pedidos por minuto, elegibilidad sin confirmar, adaptador por escribir.

### 3. Pepperstone o IC Markets (cTrader / MetaTrader) — alternativa si se prefiere un broker de forex puro
- ~ Un comparador los lista como aceptando residentes de Argentina; no lo verifiqué en sus sitios. ~ Ofrecen cuenta demo y plataformas con API (cTrader Open API, MetaTrader 5 por Python), USD/JPY de rutina.
- Pros: spreads bajos, demo inmediata, hecho para forex. Contras: la API depende de la plataforma (MT5 solo corre en Windows con el terminal abierto), reguladores offshore en algunos casos, sin verificar por mí.

## Descartado
- **OANDA**: es lo que traía el código de JarvisRemote y por eso hoy es el único adaptador real que armé, pero la página oficial de elegibilidad de [OANDA Global Markets](https://help.oanda.com/bvi/en/faqs/eligible-ogm-countries-bvi.htm) lista a Chile, Colombia y México, no a Argentina (un comparador sí la nombra; las dos fuentes se contradicen). Hasta que OANDA lo confirme por escrito, no lo consideres.

## Recomendación
Empezar por **IBKR** (la única con elegibilidad confirmada en fuente oficial) y, en paralelo, preguntarle a IG si acepta Argentina. Elegido el broker, sumar su adaptador (un archivo en `broker.py` y su lector de velas en `data.py`; los tests ya cubren el contrato con el simulado). Nada de esto toca el resto: señales, backtest y aprobaciones ya funcionan con el simulado.

Antes de abrir cualquier cuenta (según un comparador, no verificado por mí): Argentina no tiene brokers de forex minorista con licencia local (la CNV no los habilita), los brokers del exterior declaran a ARCA por intercambio automático y las ganancias tributan; consultar con un contador.
