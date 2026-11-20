# TraefikEnjoyers

Wild cam observation loggers for NERDS uc (DSE course).

Two small server-based Python web apps. In each one you enter which animal was visible in which
stream at what time, and see the log of all entries:

| App                | Observes                    | Image                                               | Path behind Traefik | DB table                |
|--------------------|-----------------------------|-----------------------------------------------------|---------------------|-------------------------|
| **Land & Air Cam** | land- and air-based animals | `ghcr.io/stelzerkatharina/wildcam-land-air:latest`  | `/land-air/`        | `land_air_observations` |
| **Sea Cam**        | sea animals                 | `ghcr.io/stelzerkatharina/wildcam-sea:latest`       | `/sea/`             | `sea_observations`      |

Both apps store observations in a central PostgreSQL database, so every worker node shows the
same log. Each app has its own table, so the two logs stay separate.

Both images are built for **linux/amd64** by GitHub Actions
([`.github/workflows/docker-image.yml`](../.github/workflows/docker-image.yml)) on every push to
`main`, and are tagged `latest` and `<commit sha>`. Pull requests are built and smoke-tested but
not published.

## Layout

```
wildcam/
  common/wildcam_core.py   shared server: storage, form handling, HTML, HTTP(S)
  land-air/app.py          Land & Air Cam config + entry point
  land-air/Dockerfile
  sea/app.py               Sea Cam config + entry point
  sea/Dockerfile
  requirements.txt
  compose.yaml             both apps + Traefik + PostgreSQL in one environment
  .env.example
```

## Running both apps together

```sh
cd wildcam
cp .env.example .env            # set POSTGRES_PASSWORD
docker compose up -d            # pull the published amd64 images (on the amd64 VMs)
docker compose up -d --build    # or build from source for your own machine (e.g. Apple Silicon)
```

- Land & Air Cam: <http://localhost/land-air/>
- Sea Cam: <http://localhost/sea/>

Traefik routes requests by path prefix. Each app gets its prefix through `BASE_PATH`, so its form
and redirects stay under that prefix. To use the central DB VM instead of the bundled PostgreSQL
container, set `DATABASE_URL` in `.env`.

The published images are amd64 only. On an Apple Silicon Mac, use `--build`. Pulled images also
run there, but only under emulation.

## Building a single image

The build context is the `wildcam/` directory, because both images include `common/`:

```sh
cd wildcam
docker build -f land-air/Dockerfile -t wildcam-land-air .
docker build -f sea/Dockerfile      -t wildcam-sea .

# the same image the pipeline builds, from any machine
docker buildx build --platform linux/amd64 -f sea/Dockerfile -t wildcam-sea:amd64 --load .
```

## Running without Docker (development)

```sh
cd wildcam
pip install -r requirements.txt
PYTHONPATH=common python land-air/app.py                  # http://localhost:8080/
PYTHONPATH=common BASE_PATH=/sea PORT=8081 python sea/app.py   # http://localhost:8081/sea/
```

## Configuration (environment variables)

| Variable       | Default   | Meaning                                                                              |
|----------------|-----------|--------------------------------------------------------------------------------------|
| `DATABASE_URL` | unset     | `postgresql://USER:PASSWORD@HOST:5432/DBNAME`. Unset = in-memory only (dev).         |
| `BASE_PATH`    | unset     | Path prefix to serve under, e.g. `/sea`. Unset = serve at `/`.                       |
| `PORT`         | `8080`    | Port to listen on.                                                                   |
| `TLS_CERTFILE` | unset     | Path to certificate. Together with `TLS_KEYFILE` switches on HTTPS.                  |
| `TLS_KEYFILE`  | unset     | Path to private key.                                                                 |

`GET /health` always answers at `/health` (and also at `BASE_PATH/health`). The image
`HEALTHCHECK` uses it.

## Migrating from the single-image setup

- The old image `ghcr.io/stelzerkatharina/traefikenjoyers` is no longer updated. Deployments need
  to switch to the two images above.
- Earlier observations stay in the old `observations` table. Neither app reads that table.
