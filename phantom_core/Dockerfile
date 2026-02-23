FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    fastapi 'uvicorn[standard]' pydantic httpx requests websockets \
    psutil numpy pyyaml cryptography pyjwt

FROM python:3.11-slim

RUN groupadd -r phantom && useradd -r -g phantom phantom

COPY --from=builder /install /usr/local

WORKDIR /app
COPY phantom_core/ phantom_core/
COPY phantom_protocol/ phantom_protocol/
COPY security_framework/ security_framework/
COPY socket_infrastructure/ socket_infrastructure/
COPY run.py run_integrated_phantom.py ./

RUN mkdir -p /app/data /app/certs && chown -R phantom:phantom /app

ENV PYTHONPATH=/app \
    PHANTOM_HOST=0.0.0.0 \
    PHANTOM_PORT=8080 \
    PHANTOM_SECURITY=basic \
    PHANTOM_STATE_DIR=/app/data

EXPOSE 8080 8081

USER phantom

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

ENTRYPOINT ["python", "run.py"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
