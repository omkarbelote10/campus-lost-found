# Campus Lost & Found

Campus Lost & Found is a web application for reporting, finding, matching, and securely returning lost items on a university campus.

The project contains:

- A Next.js frontend
- A FastAPI backend
- PostgreSQL with PostGIS and pgvector
- An ML and evaluation workspace

If you are new to the project, section 10 explains the architecture: what each service does, how a request flows from the browser to the database, and where to make a given change.

## 1. Prerequisites

The easiest way to run the complete project is with Docker. Install these tools before continuing:

- Git: https://git-scm.com/downloads
- Docker Desktop: https://www.docker.com/products/docker-desktop/

You do not need to install PostgreSQL, Python, or Node.js separately when using Docker Compose.

### Windows requirements

- Windows 10 or Windows 11
- Docker Desktop configured to use the Linux engine
- Internet access for the first image build
- At least 8 GB of available RAM recommended
- At least 10 GB of free disk space recommended

After installing Docker Desktop, open it and wait until the status says **Engine running**.

## 2. Clone the repository

Open **Command Prompt** or **PowerShell** and run:

```cmd
git clone <repository-url>
cd <repository-folder>
```

Replace `<repository-url>` with the URL of this repository. For example:

```cmd
git clone https://github.com/your-account/your-repository.git
cd your-repository
```

The folder containing this README must also contain:

```text
docker-compose.yml
backend\
database\
frontend\
ml\
```

## 3. Start the project

From the repository root, run:

```cmd
docker compose up -d --build
```

The first build can take several minutes because Docker downloads the Python and Node.js dependencies and builds the database image.

The command starts three services:

| Service | URL or port | Purpose |
| --- | --- | --- |
| Frontend | http://localhost:3000 | Next.js web application |
| Backend | http://localhost:8000 | FastAPI API |
| API docs | http://localhost:8000/docs | Swagger API documentation |
| PostgreSQL | localhost:5432 | Application database |

The database image includes both PostGIS and pgvector, which are required by the schema.

## 4. Check that the project is running

Run:

```cmd
docker compose ps
```

You should see these services running:

```text
postgres
backend
frontend
```

The PostgreSQL service should show `healthy`.

You can also test the backend health endpoint:

```cmd
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

Open the frontend in a browser:

```text
http://localhost:3000
```

## 5. Use the application

### Create an account

1. Open http://localhost:3000/register.
2. Enter your full name.
3. Enter an email ending with `@college.edu`.
4. Enter a password with at least 8 characters.
5. Confirm the password.
6. Select **Create account**.

The default campus email domain is `college.edu`.

### Sign in

1. Open http://localhost:3000/login.
2. Enter the registered campus email and password.
3. Select **Sign in**.

### Report a lost item

1. Sign in first.
2. Open http://localhost:3000/report/lost.
3. Enter the item title, description, category, campus zone, and date.
4. Optionally choose up to 3 image files or drag them into the upload area.
5. Select **Report Lost Item**.

### Report a found item

1. Sign in first.
2. Open http://localhost:3000/report/found.
3. Enter the item title, description, category, campus zone, and date.
4. Optionally choose up to 3 image files or drag them into the upload area.
5. Select **Report Found Item**.

Marking an item as high value hides its photos from everyone except you until a claim is verified.

### Browse items

Open http://localhost:3000/feed to browse and filter reported items.

## 6. Useful Docker commands

Run the project in the background:

```cmd
docker compose up -d
```

View service status:

```cmd
docker compose ps
```

View all logs:

```cmd
docker compose logs
```

View logs for one service:

```cmd
docker compose logs backend
docker compose logs frontend
docker compose logs postgres
```

Follow logs live:

```cmd
docker compose logs -f backend
```

Stop the services without deleting database data:

```cmd
docker compose stop
```

Start previously stopped services:

```cmd
docker compose start
```

Stop and remove the containers and network:

```cmd
docker compose down
```

Rebuild after changing dependencies or Dockerfiles:

```cmd
docker compose up -d --build
```

## 7. Updating the project

Before updating, stop or leave the project running as needed. From the repository root:

```cmd
git pull
docker compose up -d --build
```

Do not delete the Docker volume unless you intentionally want to delete the local database.

## 8. Troubleshooting

### Docker command is not recognized

Install Docker Desktop, restart Command Prompt or PowerShell, and verify:

```cmd
docker --version
docker compose version
```

### Docker engine is not running

Open Docker Desktop and wait for **Engine running**, then retry:

```cmd
docker compose up -d --build
```

### Frontend does not open on port 3000

Check the frontend logs:

```cmd
docker compose logs frontend
```

If another application uses port 3000, stop that application or change the frontend port mapping in `docker-compose.yml`.

### Backend does not start

Check the backend logs:

```cmd
docker compose logs backend
```

The backend waits for PostgreSQL to become healthy before starting.

### Database initialization fails

Check the PostgreSQL logs:

```cmd
docker compose logs postgres
```

If this is a new local installation and you do not need existing local data, recreate the database volume:

```cmd
docker compose down

docker volume rm lost_found_postgres_data

docker compose up -d --build
```

Warning: removing the volume permanently deletes the local PostgreSQL data.

### Registration or reporting returns 401

Sign in again at:

```text
http://localhost:3000/login
```

Then return to the report page. The application requires a valid login token for protected actions.

### Registration returns a campus email error

Use an email ending in:

```text
@college.edu
```

The allowed domain is configured by `CAMPUS_EMAIL_DOMAIN` in `docker-compose.yml`.

## 9. Optional manual development setup

Docker Compose is the recommended setup. For frontend-only work, you can also run the Next.js development server locally:

```cmd
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000.

The backend and database must still be running for login, registration, feeds, and reports to work. The frontend calls the backend directly at the URL in `NEXT_PUBLIC_API_URL` (`http://localhost:8000/api` by default), so that origin must be listed in the backend's `ALLOWED_ORIGINS`. Serving the app from a different host, such as a LAN address, requires adding that origin to `ALLOWED_ORIGINS` as well.

## 10. Architecture

This section explains how the pieces fit together. Read it before making your first change.

### 10.1 System overview

Three containers run side by side. The browser talks to two of them directly: it loads pages from the frontend and calls the backend API itself, so the frontend is never a proxy for API traffic.

```text
                 +------------------------------------------+
                 |                Browser                    |
                 |   React pages + JWT held in localStorage   |
                 +-------+---------------------------+-------+
      page HTML / JS     |                           |  JSON + multipart over HTTP
                         v                           v
        +----------------------------+   +------------------------------+
        |  frontend (Next.js 14)     |   |  backend (FastAPI)           |
        |  localhost:3000            |   |  localhost:8000              |
        |  App Router pages          |   |  /api/auth    /api/items     |
        |  Zustand store             |   |  /api/matches /api/claims    |
        |  axios client              |   |  /api/admin                  |
        +----------------------------+   |  /uploads (static images)    |
                                         +---------------+--------------+
                                                         |  SQLAlchemy
                                                         v
                                         +------------------------------+
                                         |  postgres 16                 |
                                         |  localhost:5432              |
                                         |  pgvector + PostGIS          |
                                         |  users, items, matches,      |
                                         |  claims                      |
                                         +------------------------------+

        +--------------------------------------------------------------+
        |  ml/  - offline workspace, not a running service.             |
        |  SigLIP embeddings, OCR mining, ranking, benchmark metrics.   |
        |  Run by hand; it does not serve API requests.                 |
        +--------------------------------------------------------------+
```

### 10.2 The three services

| Service | Stack | Responsibility |
| --- | --- | --- |
| `frontend` | Next.js 14 App Router, TypeScript, Tailwind, Zustand, axios | Renders every page, holds the session token, calls the backend |
| `backend` | FastAPI, SQLAlchemy 2, Pydantic v2, python-jose, bcrypt | Validates input, enforces authorization, stores items, scores matches, serves uploaded images |
| `postgres` | PostgreSQL 16 with pgvector and PostGIS | Stores all persistent data, including the 768-dimension embedding columns |

The `ml/` folder is a fourth part of the project but not a fourth container. It is a standalone workspace you run manually. See section 10.7.

### 10.3 Project structure

```text
backend/
  app/
    main.py            App startup: CORS, /uploads mount, router registration, /health
    core/
      config.py        All settings and environment variables (pydantic-settings)
      database.py      SQLAlchemy engine, SessionLocal, get_db dependency
      security.py      Password hashing, JWT issue and verify, auth dependencies
    api/
      auth.py          POST /register, POST /login, GET /me
      items.py         POST /report, GET /feed, GET /{id}, GET /
      matches.py       POST /find, GET /{id}, GET /item/{id}
      claims.py        Challenge create, respond, approve; QR handshake verify
      admin.py         Vault listing and processing, QR scan audit, stats
    models/            SQLAlchemy tables: user.py, item.py, match.py (Match + Claim)
    schemas/           Pydantic request and response shapes
    services/
      scoring.py       ScoringEngine: the whole match formula lives here
    utils/
      validators.py    Campus email check, OCR token extraction, file type check
  uploads/             Uploaded images on disk, served at /uploads
  tests/               pytest suite, runs against temporary SQLite

frontend/
  src/
    app/               App Router pages: /, /login, /register, /dashboard,
                       /feed, /report/lost, /report/found, plus NavBar and layout
    services/api.ts    Single axios client, auth interceptors, all API call wrappers
    hooks/useStore.ts  Zustand stores: useAuthStore, useItemsStore, useMatchesStore

database/
  schema.sql           Tables, enums, indexes, HNSW vector indexes; runs on first boot
  Dockerfile           PostgreSQL 16 image with pgvector and PostGIS installed

ml/
  src/embeddings/      SigLIP wrapper, OCR token miner
  src/preprocessing/   Image and text preparation
  src/ranking/         Hybrid scorer used by the benchmark
  src/retrieval/       In-memory cosine similarity index
  src/evaluation/      Recall@K, MRR, Precision@K, NDCG@K and the eval runner

docker-compose.yml     Wires the three services, the database volume, and the env vars
```

### 10.4 How a request travels

Take "report a lost item" as the example.

1. The page at `/report/lost` builds a `FormData` with the text fields and up to three files.
2. It calls `itemService.reportItem(formData)` in [api.ts](frontend/src/services/api.ts).
3. The axios request interceptor reads the JWT from `localStorage` and adds `Authorization: Bearer <token>`.
4. The browser sends the request to `http://localhost:8000/api/items/report`. This is a cross-origin call, so the origin must be listed in the backend's `ALLOWED_ORIGINS`.
5. FastAPI resolves the `get_current_user_id` dependency, which decodes the token and yields the user id, or returns 401.
6. [items.py](backend/app/api/items.py) validates the type, category, file extensions, and file sizes, writes each image under a generated `{user_id}_{uuid}.{ext}` name, and inserts the row.
7. The response comes back as an `ItemResponse`. If the API ever returns 401, the axios response interceptor clears the store and sends the user to `/login?redirect=<current path>`.

The important structural point: the browser calls the backend directly. There is no Next.js API route in between, which is why CORS and `NEXT_PUBLIC_API_URL` both matter whenever you serve the app from anything other than `localhost`.

### 10.5 Authentication and roles

- Passwords are hashed with bcrypt. Input is truncated to bcrypt's 72-byte limit rather than raising.
- Login and registration both return a JWT signed with HS256 carrying `sub` (the user id) and `role`. It is valid for 7 days and there is no refresh flow.
- The token lives in `localStorage`, so it is per-origin. Serving the app from a different host means a separate session.
- The backend has three auth dependencies in [security.py](backend/app/core/security.py): `get_current_user_id` requires a token, `get_optional_user_id` allows anonymous callers, and `require_admin` additionally requires `role == "SECURITY_ADMIN"`.
- Roles are `STUDENT`, `STAFF`, and `SECURITY_ADMIN`. Registration always creates a `STUDENT`. No endpoint promotes a user, so to exercise the admin and handover endpoints you must update the row directly, then sign in again to get a token carrying the new role:

```cmd
docker compose exec postgres psql -U postgres -d clfis_db -c "UPDATE users SET role = 'SECURITY_ADMIN' WHERE email = 'you@college.edu';"
```

### 10.6 Data model and item lifecycle

Four tables, defined twice: in `database/schema.sql` for the real Postgres database, and as SQLAlchemy models under `backend/app/models/` for the application. Keep the two in sync when you add a column.

| Table | Holds | Notable columns |
| --- | --- | --- |
| `users` | Accounts | `role`, `karma_score` (defaults to 100) |
| `items` | One lost or found report | `type`, `category`, `campus_zone`, `incident_time`, `image_urls[]`, `ocr_tokens[]`, `image_embedding vector(768)`, `text_embedding vector(768)`, `is_high_value`, `status` |
| `matches` | One scored lost and found pair | every score component plus `total_score` and `status` |
| `claims` | One attempt to claim a match | `challenge_question`, `claimant_answer`, `is_challenge_approved`, `handshake_qr_token`, `resolved_at` |

An item moves through `status` like this:

```text
OPEN --POST /api/matches/find--> match rows created (HIGH_CONFIDENCE or POTENTIAL)
  |
  |-- claimant: POST /api/claims/challenge/create   (question + answer)
  |-- owner of the found item: POST /api/claims/challenge/approve
  |        issues a QR token valid for 15 minutes
  |-- SECURITY_ADMIN: POST /api/claims/handshake/verify
  |        records who handed the item over and stamps resolved_at
  v
RESOLVED

OPEN and older than 45 days --POST /api/admin/vault/process--> UNCLAIMED_VAULT
```

Only the person who reported the found item may approve a claim against it, and only an admin token may complete the handover. Those two checks are what keep the flow from being self-serve.

Items flagged `is_high_value` have their `image_urls` blanked for everyone except the owner. The masking is applied to the response object in both `GET /feed` and `GET /{item_id}`, never to the ORM row, since mutating the row would let a later flush erase the URLs from the database.

### 10.7 The matching engine

All of the scoring lives in [scoring.py](backend/app/services/scoring.py). `POST /api/matches/find` loads every `OPEN` found item in the same category as your lost item, scores each pair, and saves the ones that clear a threshold.

```text
S_total = (w_v * S_visual + w_t * S_text + w_c * S_category) * (D_spatial * D_temporal) + B_ocr
```

| Term | How it is computed |
| --- | --- |
| `S_visual` | Cosine similarity of the two image embeddings |
| `S_text` | Cosine similarity of the two text embeddings |
| `S_category` | 1.0 on an exact category match, otherwise 0.0 |
| `D_spatial` | From GPS by haversine distance when both items have coordinates; otherwise 1.0 for the same zone, 0.8 for adjacent zones, 0.4 for distant ones |
| `D_temporal` | `exp(-0.05 * days_between)`, and 0.1 when the found time precedes the lost time |
| `B_ocr` | A flat 0.25 when the two items share any OCR token |

Weights are 0.45 visual, 0.30 text, and 0.25 category when both items have images, and rebalance to 0, 0.70, and 0.30 when either does not. A total at or above 0.80 is `HIGH_CONFIDENCE`, at or above 0.55 is `POTENTIAL`, and anything lower is rejected and never written.

One thing to know before you judge match quality: **the API does not currently populate the embedding columns.** `POST /api/items/report` stores images and OCR tokens but leaves `image_embedding` and `text_embedding` null, so `S_visual` and `S_text` evaluate to 0 and live matching effectively runs on category, location, time, and OCR overlap. The SigLIP pipeline under `ml/` exists and is exercised by the benchmark runner, but nothing in the request path calls it. Wiring it in is the natural next piece of work, and it belongs in `report_item` in [items.py](backend/app/api/items.py).

### 10.8 Configuration

Settings are read by [config.py](backend/app/core/config.py) from the environment, with defaults in code. The values that matter day to day are set in `docker-compose.yml`.

| Variable | Where it is set | Default | Effect |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend service | points at the `postgres` container | Which database the API uses |
| `SECRET_KEY` | backend service | a placeholder | Signs every JWT. Change it for any real deployment |
| `CAMPUS_EMAIL_DOMAIN` | backend service | `college.edu` | Which email domain may register |
| `ALLOWED_ORIGINS` | backend, code default | the four localhost origins | Which origins may call the API |
| `MAX_UPLOAD_SIZE` | code default | 10 MB | Per-file upload ceiling |
| `UPLOAD_DIR` | code default | `backend/uploads` | Where images are written and served from |
| `NEXT_PUBLIC_API_URL` | frontend service | `http://localhost:8000/api` | The API base the browser calls |

Changing `NEXT_PUBLIC_API_URL` without adding the matching origin to `ALLOWED_ORIGINS` produces requests that fail in the browser but succeed from `curl`. That mismatch is the most common setup problem.

### 10.9 Where to make a given change

| You want to | Edit |
| --- | --- |
| Add or change an API endpoint | The matching file in [backend/app/api/](backend/app/api/) |
| Add a field to an item | [models/item.py](backend/app/models/item.py), [schemas/item.py](backend/app/schemas/item.py), and [database/schema.sql](database/schema.sql) |
| Change how matches are scored | [services/scoring.py](backend/app/services/scoring.py) |
| Change campus zones or their adjacency | `are_adjacent_zones` in [services/scoring.py](backend/app/services/scoring.py) and `parse_campus_zone` in [utils/validators.py](backend/app/utils/validators.py) |
| Change a page or add a route | A folder under [frontend/src/app/](frontend/src/app/) |
| Add a new API call from the frontend | [frontend/src/services/api.ts](frontend/src/services/api.ts) |
| Change what the session stores | [frontend/src/hooks/useStore.ts](frontend/src/hooks/useStore.ts) |
| Change auth rules or token lifetime | [core/security.py](backend/app/core/security.py) and [core/config.py](backend/app/core/config.py) |

Both containers run with the source mounted and hot reload enabled, so backend and frontend edits apply without a rebuild. Rebuild only after changing `requirements.txt`, `package.json`, or a Dockerfile. Changes to `database/schema.sql` apply only to a fresh volume, because the init script runs once. The backend's `create_all` adds missing tables on startup but does not alter existing ones.

## 11. Testing and checks

Frontend type check:

```cmd
cd frontend
npm run type-check
```

Frontend production build:

```cmd
cd frontend
npm run build
```

Frontend lint:

```cmd
cd frontend
npm run lint
```

Backend tests. These run against a temporary SQLite database, so no Postgres or Docker is needed:

```cmd
cd backend
pip install -r requirements.txt
pytest tests/
```

ML evaluation:

```cmd
python ml/src/evaluation/run_eval.py
```

## 12. Stopping and restarting the project

To stop the project:

```cmd
docker compose down
```

To start it again later:

```cmd
cd /d "path\to\your\repository"
docker compose up -d
```

Then open:

```text
http://localhost:3000
```
