# Deployment

Docker Compose is the supported way to run this project — locally or on a
single-host deployment. There is no Kubernetes manifest, cloud IaC, or
managed-service configuration in this repository.

## 1. Prerequisites

- Git
- Docker Desktop (or Docker Engine + Compose plugin on Linux)
- 8 GB+ RAM and 10 GB+ free disk recommended (the backend image pulls
  PyTorch + CUDA wheels and two HuggingFace model checkpoints on first run)
- (Optional, for GPU inference) NVIDIA Container Toolkit + a CUDA-capable GPU

You do not need PostgreSQL, Python, or Node.js installed separately — Docker
Compose builds all three service images.

## 2. Start the stack

```bash
git clone <repository-url>
cd <repository-folder>
docker compose up -d --build
```

This starts three services:

| Service | URL / port | Purpose |
| --- | --- | --- |
| `frontend` | http://localhost:3000 | Next.js web app |
| `backend` | http://localhost:8000 | FastAPI API |
| — | http://localhost:8000/docs | Swagger UI |
| `postgres` | localhost:5432 | Application database |

Verify:
```bash
docker compose ps                       # postgres should show "healthy"
curl http://localhost:8000/health       # {"status":"healthy", "embeddings": {...}}
```

The first build can take several minutes — it downloads the PyTorch CUDA
wheels and both embedding models (SigLIP + DINOv2, ≈1GB combined) on the
first item report, not at build time (models load lazily).

## 3. Configuration

Settings are read from the environment by `backend/app/core/config.py`, with
code defaults. `docker-compose.yml` sets the values that matter day to day:

| Variable | Set in | Default | Effect |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend service | points at the `postgres` container | Which database the API uses |
| `SECRET_KEY` | backend service | a placeholder | Signs every JWT — **change for any real deployment** |
| `CAMPUS_EMAIL_DOMAIN` | backend service | `college.edu` | Which email domain may register |
| `ALLOWED_ORIGINS` | code default | the four localhost origins | Which origins may call the API (CORS) |
| `EMBEDDING_DEVICE` | backend service | `auto` | `auto` picks CUDA when available and falls back to CPU; an explicit `cuda` fails loudly instead of silently degrading to CPU |
| `HF_TOKEN` | backend service, from `.env` | empty | Only needed for gated HuggingFace weights (e.g. a gated DINOv3 checkpoint); leave empty for the default ungated models |
| `MAX_UPLOAD_SIZE` | code default | 10 MB | Per-file upload ceiling |
| `UPLOAD_DIR` | code default | `backend/uploads` | Where images are written and served from |
| `NEXT_PUBLIC_API_URL` | frontend service | `http://localhost:8000/api` | The API base the **browser** calls directly |

Copy `.env.example` to `.env` at the repo root for `HF_TOKEN` and any local
overrides — `.env` is gitignored and is read by `docker-compose.yml`'s
`${HF_TOKEN:-}` interpolation.

**Common misconfiguration**: changing `NEXT_PUBLIC_API_URL` without adding the
matching origin to `ALLOWED_ORIGINS` produces requests that fail in the
browser (CORS) but succeed from `curl`. Both `localStorage` (the JWT) and CORS
are per-origin, so serving the app from a LAN address or a different host
needs that origin added to `ALLOWED_ORIGINS` as well.

## 4. GPU vs CPU inference

`backend/Dockerfile` installs `torch==2.2.2` from the CUDA 12.1 wheel index.
`docker-compose.yml`'s `backend` service requests an NVIDIA GPU reservation
(`deploy.resources.reservations.devices`), which requires the NVIDIA
Container Toolkit on the host. Without it, or without a GPU present, the
container still starts fine and `EMBEDDING_DEVICE=auto` falls back to CPU —
inference is just several times slower. To build a smaller CPU-only image,
swap the `cu121` wheel index in `backend/Dockerfile` for `.../whl/cpu`
(~200MB vs. the CUDA build).

The `huggingface_cache` named volume persists downloaded model weights across
container recreates, so they aren't re-fetched on every `docker compose up`.

## 5. Everyday Docker commands

```bash
docker compose up -d              # start in the background
docker compose ps                 # service status
docker compose logs               # all logs
docker compose logs -f backend    # follow one service's logs
docker compose stop               # stop, keep data
docker compose start              # resume
docker compose down               # stop and remove containers + network (keeps the volume)
docker compose up -d --build      # rebuild after changing requirements.txt / package.json / a Dockerfile
```

Both `backend` and `frontend` run with source bind-mounted and hot reload
enabled (`--reload` for uvicorn, `next dev`), so ordinary code edits apply
without a rebuild.

## 6. Promoting a user to STAFF

There is no registration flag or admin endpoint for this — the `STUDENT`
default is hardcoded, and the only other role in this codebase's `user_role`
enum is `STAFF` (see [architecture.md](architecture.md) §5 — there is no
`SECURITY_ADMIN` role here despite the spec describing one). Update the row
directly, then sign in again to get a token carrying the new role:

```bash
docker compose exec postgres psql -U postgres -d clfis_db \
  -c "UPDATE users SET role = 'STAFF' WHERE email = 'you@college.edu';"
```

## 7. Applying a database migration

`schema.sql` only runs once, against a fresh volume. To apply a later change
(e.g. the embedding-column fix in `database/migrations/`) to an existing
database:

```bash
docker compose exec -T postgres psql -U postgres -d clfis_db \
  < database/migrations/003_restore_768_image_embedding.sql
```

If the migration cleared or resized an embedding column, repopulate it and
rebuild matches:

```bash
docker compose exec backend python scripts/reembed.py
```

See [database.md](database.md) for what each migration does and why.

## 8. Resetting local data

```bash
docker compose down
docker volume rm lost_found_postgres_data
docker compose up -d --build
```

**This permanently deletes the local PostgreSQL data.** Only do this for a
fresh local install where you don't need existing data.

## 9. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `docker` not recognized | Install Docker Desktop, restart the shell, verify with `docker --version` |
| Engine not running | Open Docker Desktop, wait for "Engine running", retry |
| Frontend doesn't open on :3000 | `docker compose logs frontend`; check for a port conflict or change the frontend port mapping |
| Backend doesn't start | `docker compose logs backend`; it waits for Postgres to report healthy before starting |
| DB init fails | `docker compose logs postgres`; if it's a fresh local install, recreate the volume (§8) |
| `401` on report/registration | Sign in again at `/login`; protected actions require a valid, non-expired token |
| Campus-email error on register | Use an email ending in the configured `CAMPUS_EMAIL_DOMAIN` (default `@college.edu`) |
| Report with a photo fails with a CORS error in the browser | Usually not actually CORS — an unhandled backend 500 (e.g. an embedding-column dimension mismatch) never passes through the CORS middleware and surfaces as a CORS error client-side. Check `docker compose logs backend` for the real exception; see [database.md](database.md)'s migration note. |

## 10. Manual (non-Docker) development

Postgres and the backend must still be reachable for most frontend
functionality (login, registration, feeds, reports). For frontend-only work:

```bash
cd frontend
npm install
npm run dev
```

For backend work without Docker:
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
You'll need a reachable Postgres 16 instance with `vector` and `postgis`
extensions and `DATABASE_URL` pointed at it — e.g.:
```bash
docker run --name clfis-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=clfis_db -p 5432:5432 -d postgis/postgis:16-3.4
```
(then install `pgvector` into that container, or use `database/Dockerfile` as
a base, before running `schema.sql` against it).
