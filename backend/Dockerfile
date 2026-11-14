# API and worker image. Build from the repository root:
#   docker build -f backend/Dockerfile .
FROM python:3.12-slim

# The worker starts sandbox containers through the host's Docker daemon.
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker

COPY backend /app/backend
RUN pip install --no-cache-dir -e /app/backend
COPY sandbox /app/sandbox
COPY worker /app/worker
COPY problems /app/problems
COPY scripts /app/scripts

ENV PYTHONPATH=/app/backend:/app PYTHONUNBUFFERED=1
WORKDIR /app/backend
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
