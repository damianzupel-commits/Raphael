# Seguridad · monitoreo
- `health` del manifiesto (`raphael_seguridad.health:check`): da mal solo si la config es inválida. Lo que falta (repos autorizados, consulta de dependencias apagada) se avisa en el detalle, no tumba la brigada.
- La vigilancia defensiva publica `seguridad.alerta` en el bus; el orquestador la convierte en aviso a Damián. Alertas abiertas: comando `alertas`.
- Eventos: `seguridad.auditoria_terminada`, `seguridad.hallazgo_critico`, `seguridad.pentest_terminado`.
