# syntax=docker/dockerfile:1.7
# Imagen única para el servicio de inferencia (uvicorn) y el worker de entrenamiento (rq).
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app/src \
    ML_DATA_DIR=/data ML_ARTIFACT_DIR=/artifacts OMP_NUM_THREADS=2
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
# PyTorch CPU (imagen ligera, sin CUDA). Para GPU usar la rueda cu12x correspondiente.
ARG TORCH_VERSION=2.15.0
RUN pip install "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src ./src
COPY configs ./configs
COPY dvc.yaml start-combined.sh docker-entrypoint.sh ./
RUN useradd -r -u 10002 -g root mluser && mkdir -p /data /artifacts && chown -R 10002:0 /app /data /artifacts
# Arranca como root solo para ajustar permisos del volumen; el entrypoint baja a uid 10002.
ENTRYPOINT ["./docker-entrypoint.sh"]
EXPOSE 8001
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=5 CMD curl -fsS http://localhost:8001/health || exit 1
CMD ["uvicorn", "edumaster_ml.inference.service:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
