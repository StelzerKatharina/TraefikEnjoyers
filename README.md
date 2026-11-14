# TraefikEnjoyers

Wild cam observation logger for NERDS uc (DSE course, Task 1).

A small server-based Python web app: enter which animal was visible in which stream
at what time, and see the log of all entries. Observations are stored in a central
PostgreSQL database so every worker node shows the same log.

Image: `ghcr.io/stelzerkatharina/traefikenjoyers:latest` (built automatically by GitHub Actions on every push to `main`).

## Configuration (environment variables)

| Variable       | Default   | Meaning                                                              |
|----------------|-----------|----------------------------------------------------------------------|
| `DATABASE_URL` | unset     | `postgresql://USER:PASSWORD@HOST:5432/DBNAME`. Unset = in-memory only (dev). |
| `PORT`         | `8080`    | Port to listen on.                                                   |
| `TLS_CERTFILE` | unset     | Path to certificate. Together with `TLS_KEYFILE` switches on HTTPS.  |
| `TLS_KEYFILE`  | unset     | Path to private key.                                                 |
ithub/workflows/docker-image.yml` runs on every push to `main`:
