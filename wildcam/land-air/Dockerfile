# Build from the wildcam/ directory:  docker build -f land-air/Dockerfile .
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/StelzerKatharina/TraefikEnjoyers" \
      org.opencontainers.image.title="wildcam-land-air" \
      org.opencontainers.image.description="NERDS uc wild cam observation log for land- and air-based animals"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/wildcam_core.py land-air/app.py ./

# Plain HTTP by default: Traefik in front terminates TLS.
# Set TLS_CERTFILE / TLS_KEYFILE (and mount the files) to serve HTTPS directly instead.
# BASE_PATH (e.g. /land-air) serves the app under a path prefix behind Traefik.
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=3 \
  CMD ["python", "-c", "import sys, wildcam_core; sys.exit(wildcam_core.healthcheck())"]

CMD ["python", "app.py"]
