# Imagen del equipo del cliente. Contexto de build: la carpeta que contiene TODOS los repos raphael-*.
#   docker build -f raphael-servidor/despliegue/Dockerfile -t raphael .
FROM python:3.12-slim AS base
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
COPY raphael-harness /src/raphael-harness
COPY raphael-orquestador /src/raphael-orquestador
COPY raphael-atencion /src/raphael-atencion
COPY raphael-encargos /src/raphael-encargos
COPY raphael-cobros /src/raphael-cobros
COPY raphael-agenda /src/raphael-agenda
COPY raphael-avisos /src/raphael-avisos
COPY raphael-servidor /src/raphael-servidor
RUN pip install /src/raphael-harness /src/raphael-orquestador /src/raphael-atencion /src/raphael-encargos \
        /src/raphael-cobros /src/raphael-agenda /src/raphael-avisos /src/raphael-servidor

# Si un test falla, la imagen NO se construye y el actualizador deja corriendo la versión anterior.
FROM base AS prueba
RUN pip install pytest && cd /src && for r in raphael-*/; do (cd "$r" && python -m pytest -q -p no:cacheprovider) || exit 1; done && touch /pruebas-ok

FROM base AS final
COPY --from=prueba /pruebas-ok /pruebas-ok
RUN rm -rf /src && useradd --create-home raphael && mkdir /datos && chown raphael /datos
USER raphael
ENV RAPHAEL_DIR=/datos
VOLUME /datos
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/salud')"
CMD ["python", "-m", "raphael_servidor", "correr", "--puerto", "8080"]
