FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Plain HTTP by default: Traefik in front terminates TLS.
# Set TLS_CERTFILE / TLS_KEYFILE (and mount the files) to serve HTTPS directly instead.
ENV PORT=8080
EXPOSE 8080

CMD ["python", "app.py"]
