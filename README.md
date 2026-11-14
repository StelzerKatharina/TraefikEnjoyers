# TraefikEnjoyers

Wild cam observation logger for NERDS uc (DSE course, Task 1).

A small server-based Python web app: enter which animal was visible in which stream
at what time, and see the log of all entries. Observations are stored in a central
PostgreSQL database so every worker node shows the same log.

Image: `ghcr.io/stelzerkatharina/traefikenjoyers:latest` (built automatically by GitHub Actions on every push to `main`).

## How it fits together

```
Internet --> Proxmox host (NAT) --> Traefik VM --> worker1 / worker2 / worker3  (this container)
                                                          |
                                                          v
                                                   DB VM (PostgreSQL, static IP)
```

The container speaks plain HTTP on port 8080 and Traefik terminates HTTPS in front of it.
For running a single worker without Traefik, the container can also serve HTTPS directly (see below).

## Configuration (environment variables)

| Variable       | Default   | Meaning                                                              |
|----------------|-----------|----------------------------------------------------------------------|
| `DATABASE_URL` | unset     | `postgresql://USER:PASSWORD@HOST:5432/DBNAME`. Unset = in-memory only (dev). |
| `PORT`         | `8080`    | Port to listen on.                                                   |
| `TLS_CERTFILE` | unset     | Path to certificate. Together with `TLS_KEYFILE` switches on HTTPS.  |
| `TLS_KEYFILE`  | unset     | Path to private key.                                                 |

## 1. Database server VM

PostgreSQL as a Podman container (counts for the Podman bonus). On the DB VM:

```bash
sudo apt update && sudo apt install -y podman
sudo podman run -d --name wildcam-db --restart always -p 5432:5432 \
  -e POSTGRES_DB=wildcam -e POSTGRES_USER=wildcam -e POSTGRES_PASSWORD=change-me \
  -v wildcam-db-data:/var/lib/postgresql/data \
  docker.io/library/postgres:16
sudo systemctl enable --now podman-restart   # start the container again after a reboot
```

Note the static IP of the DB VM (e.g. `10.0.0.20`). The app creates its table on first start.

## 2. Worker VM: pull and run the image

```bash
sudo apt update && sudo apt install -y docker.io
sudo docker pull ghcr.io/stelzerkatharina/traefikenjoyers:latest
sudo docker run -d --name wildcam --restart unless-stopped -p 8080:8080 \
  -e DATABASE_URL=postgresql://wildcam:change-me@10.0.0.20:5432/wildcam \
  ghcr.io/stelzerkatharina/traefikenjoyers:latest
```

Check: `curl http://localhost:8080/health` prints `ok`. The page footer shows which worker served the request, which makes load balancing visible later.

To update a worker after a new push: `docker pull ... && docker rm -f wildcam && docker run ...` (same command as above).

### Optional: HTTPS directly from the container (no Traefik yet)

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
sudo docker run -d --name wildcam --restart unless-stopped -p 8443:8443 \
  -e PORT=8443 -e TLS_CERTFILE=/certs/cert.pem -e TLS_KEYFILE=/certs/key.pem \
  -v "$PWD/cert.pem:/certs/cert.pem:ro" -v "$PWD/key.pem:/certs/key.pem:ro" \
  -e DATABASE_URL=postgresql://wildcam:change-me@10.0.0.20:5432/wildcam \
  ghcr.io/stelzerkatharina/traefikenjoyers:latest
```

## 3. GitHub Actions workflow

`.github/workflows/docker-image.yml` runs on every push to `main`:

1. builds the Docker image,
2. pushes it to the GitHub Container Registry as `:latest` and `:<commit sha>`.

One-time setup: after the first run, open the package on GitHub (repo page, right side, "Packages"),
go to *Package settings* and set visibility to **Public**. Then the workers can pull without logging in.

## Local development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python app.py                      # http://localhost:8080, in-memory storage
python app.py --certfile cert.pem --keyfile key.pem --port 8443   # HTTPS
```

Against a local database: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=secret -e POSTGRES_USER=wildcam -e POSTGRES_DB=wildcam postgres:16`
and `DATABASE_URL=postgresql://wildcam:secret@localhost:5432/wildcam python app.py`.
