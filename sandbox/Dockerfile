FROM python:3.12-slim

RUN pip install --no-cache-dir "numpy>=2,<3" "scipy>=1.14,<2"

COPY harness.py /opt/harness.py

# One BLAS thread: the container gets one CPU and a small pid limit.
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "/opt/harness.py"]
