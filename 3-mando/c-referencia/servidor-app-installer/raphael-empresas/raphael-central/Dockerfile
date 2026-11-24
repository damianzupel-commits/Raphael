FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1
COPY . /src
RUN pip install /src && useradd -m central && mkdir /datos && chown central /datos
USER central
WORKDIR /datos
ENV CENTRAL_BASE=/datos/central.sqlite
EXPOSE 8070
CMD ["python", "-m", "raphael_central", "--puerto", "8070"]
