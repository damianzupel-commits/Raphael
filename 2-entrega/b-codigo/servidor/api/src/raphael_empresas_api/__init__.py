"""API HTTP de Raphael Empresas para la app Android de la dueña (contrato en API.md).

Se para sobre un `Runtime` ya armado (`raphael_empresas.boot.start`) y solo hace lo que la dueña podría hacer en el
panel: ver y decidir pendientes, hablar con la Secretaria, ver y cambiar el estado de encargos, ver turnos, señas,
dudas y el catálogo. Nada de lo que decide pasa por fuera del Policy Engine del harness.
"""

__version__ = "1.0.0"
API_VERSION = 1
