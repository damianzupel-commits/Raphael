FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1
COPY . /src
RUN pip install /src && useradd -m relay && mkdir /datos && chown relay /datos
USER relay
WORKDIR /datos
ENV RELAY_BASE=/datos/relay.sqlite RELAY_INSTALACIONES=/datos/instalaciones.yaml
EXPOSE 8090
CMD ["python", "-m", "raphael_relay", "--puerto", "8090"]
