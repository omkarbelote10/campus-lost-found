# Architecture

Campus Lost & Found (CLFIS) is a three-service web application plus a standalone
offline ML workspace. This document describes what each piece does, how a
request travels through the system, and where the real implementation differs
from the original spec.

## 1. System overview

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
                                         |  pgvector + PostGIS          |
                                         |  users, items, matches,      |
                                         |  claims                      |
                                         +------------------------------+

        +--------------------------------------------------------------+
        |  ml/  - offline workspace, not a running service              |
        |  SigLIP text embeddings, OCR mining, ranking, eval metrics    |
        |  Run by hand; does not serve API requests                     |
        +--------------------------------------------------------------+
```

The browser talks to two containers directly: it loads pages from `frontend`
and calls `backend` itself over `NEXT_PUBLIC_API_URL`. The frontend is never a
proxy for API traffic — there is no Next.js API route in between, which is why
CORS (`ALLOWED_ORIGINS`) matters whenever the app is served from anything other
than `localhost`.

## 2. The three services

| Service | Stack | Responsibility |
| --- | --- | --- |
| `frontend` | Next.js 14 App Router, TypeScript, Tailwind, Zustand, axios | Renders every page, holds the session token, calls the backend |
| `backend` | FastAPI, SQLAlchemy 2, Pydantic v2, python-jose, bcrypt, transformers/torch | Validates input, enforces authorization, stores items, generates embeddings, scores matches, serves uploaded images |
| `postgres` | PostgreSQL 16 with pgvector and PostGIS | Stores all persistent data, including the 768-dimension embedding columns |

`ml/` is a fourth part of the repository but not a fourth container — it's a
manually-run workspace for offline evaluation of the matching formula (see
[ai-matching.md](ai-matching.md) §5).

## 3. Project structure

```text
backend/
  app/
    main.py            App startup: logging, CORS, /uploads mount, routers, /health
    core/
      config.py         All settings (pydantic-settings): DB, JWT, embedding models
      database.py        SQLAlchemy engine, SessionLocal, get_db dependency
      security.py        bcrypt hashing, JWT issue/verify, auth dependencies
    api/
      auth.py             POST /register, POST /login, GET /me
      items.py            POST /report, GET /feed, GET /{id}, GET /
      matches.py          POST /find, GET /mine, GET /{id}, GET /item/{id}
      claims.py           challenge/create, challenge/respond, challenge/approve
      admin.py            GET /stats
    models/               SQLAlchemy tables: user.py, item.py, match.py (Match + Claim)
    schemas/              Pydantic request/response shapes
    services/
      embeddings.py       SigLIP text tower + DINOv2 image tower, brand detection
      matching.py         Candidate retrieval + match persistence
      scoring.py          ScoringEngine: the hybrid match formula
    utils/
      validators.py       Campus email check, OCR-style identifier extraction, file type check
    scripts/
      benchmark.py         Retrieval accuracy against real uploaded photos
      reembed.py            Recompute every item's embeddings and rebuild matches
      tune.py                Sweep scoring configurations against the benchmark
  uploads/                Uploaded images on disk, served at /uploads
  tests/                  pytest suite, runs against a temporary SQLite database

frontend/
  src/
    app/                 App Router pages: /, /login, /register, /dashboard,
                         /feed, /report/lost, /report/found, plus NavBar and layout
    components/           ClaimVerifyModal, ContactRevealPanel, ItemDetailsModal, Modal
    services/api.ts        Single axios client, auth interceptors, all API call wrappers
    services/claimVerification.ts
    hooks/useStore.ts      Zustand stores (auth, items, matches)
    hooks/useItemDetail.ts

database/
  schema.sql              Tables, enums, indexes, HNSW vector indexes; runs on first boot
  Dockerfile               PostgreSQL 16 image with pgvector and PostGIS installed
  migrations/               Hand-run SQL fixes applied after schema.sql (see database.md)

ml/
  src/embeddings/          SigLIP wrapper, OCR token miner (standalone copy, see ai-matching.md)
  src/preprocessing/         Image and text preparation
  src/ranking/                Hybrid scorer mirrored from the backend
  src/retrieval/               In-memory cosine similarity index
  src/evaluation/               Recall@K, MRR, Precision@K, NDCG@K and the eval runner

docker-compose.yml         Wires the three services, the database volume, and env vars
```

## 4. How a request travels — "report a lost item"

1. The page at `/report/lost` builds a `FormData` with the text fields and up
   to three files.
2. It calls `itemService.reportItem(formData)` in `frontend/src/services/api.ts`.
3. The axios request interceptor reads the JWT from `localStorage` and adds
   `Authorization: Bearer <token>`.
4. The browser sends the request to `http://localhost:8000/api/items/report`
   (a cross-origin call — the origin must be listed in `ALLOWED_ORIGINS`).
5. FastAPI resolves the `get_current_user_id` dependency, which decodes the
   token and yields the user id, or returns 401.
6. `backend/app/api/items.py::report_item` validates type/category, saves each
   image under a generated `{user_id}_{uuid}.{ext}` name, builds a `text_embedding`
   (SigLIP) and — if a photo was attached — an `image_embedding` (DINOv2) and a
   detected `brand`, then inserts the row.
7. Matching runs immediately, in-process: `find_matches_for_item` scores the new
   item against every open counterpart in the same category and persists any
   pair clearing the `POTENTIAL` threshold (see [ai-matching.md](ai-matching.md)).
   A failure here is logged and rolled back — it never costs the user the report
   they just filed.
8. The response comes back as an `ItemResponse`. If the API ever returns 401,
   the axios response interceptor clears the store and redirects to
   `/login?redirect=<current path>`.

## 5. Authentication and roles

- Passwords are hashed with bcrypt; input is truncated to bcrypt's 72-byte
  limit rather than raising.
- Login and registration both return a JWT (HS256) carrying `sub` (user id)
  and `role`, valid for 7 days. There is no refresh-token flow.
- The token lives in `localStorage`, so a session is per-origin.
- `backend/app/core/security.py` exposes two auth dependencies actually used
  by the routers: `get_current_user_id` (requires a token) and
  `get_optional_user_id` (allows anonymous callers, e.g. browsing `/feed`).
- **Roles in the current codebase are `STUDENT` and `STAFF` only** — the
  `SECURITY_ADMIN` role and `require_admin` dependency described in the
  project's original specification (`spec.txt`) are not present in
  `app/models/user.py` or `app/core/security.py`. `/api/admin` currently
  exposes only a public `GET /stats` endpoint; there is no admin-gated vault
  or QR-handshake endpoint in this codebase.

## 6. Data model and item lifecycle

Four tables, defined in `database/schema.sql` and mirrored as SQLAlchemy
models under `backend/app/models/`. See [database.md](database.md) for full
column detail.

An item moves through `status` like this:

```text
OPEN --POST /api/items/report or POST /api/matches/find-->
    matches scored; rows persisted for HIGH_CONFIDENCE or POTENTIAL pairs
  |
  |-- claimant: POST /api/claims/challenge/create   (question + answer)
  |-- claimant: POST /api/claims/challenge/respond   (revise the answer, optional)
  |-- finder (owner of the found item): POST /api/claims/challenge/approve
  |        both items -> RESOLVED, finder's karma_score += 25
  v
RESOLVED
```

The `item_status` enum still defines `MATCH_PENDING`, `HANDOVER_SCHEDULED`,
and `UNCLAIMED_VAULT` (inherited from the original spec), but nothing in the
current API code sets or reads those values — items go straight from `OPEN`
to `RESOLVED` on claim approval. There is no vault-aging job or QR-handshake
step in this codebase; those are spec/README ambitions that were not carried
into the implementation captured in this ZIP.

Items flagged `is_high_value` have their `image_urls` blanked for everyone
except the owner. The masking is applied to the response object in both
`GET /feed` and `GET /{item_id}`, never to the ORM row — mutating the row
would let a later flush erase the URLs from the database.

## 7. Where to make a given change

| You want to | Edit |
| --- | --- |
| Add or change an API endpoint | The matching file in `backend/app/api/` |
| Add a field to an item | `models/item.py`, `schemas/item.py`, and `database/schema.sql` |
| Change how matches are scored | `services/scoring.py` |
| Change which model produces which embedding | `services/embeddings.py` and `core/config.py` |
| Change campus zones or their adjacency | `are_adjacent_zones` in `services/scoring.py` and `parse_campus_zone` in `utils/validators.py` |
| Change a page or add a route | A folder under `frontend/src/app/` |
| Add a new API call from the frontend | `frontend/src/services/api.ts` |
| Change what the session stores | `frontend/src/hooks/useStore.ts` |
| Change auth rules or token lifetime | `core/security.py` and `core/config.py` |

Both containers run with source mounted and hot reload enabled in
`docker-compose.yml`, so backend and frontend edits apply without a rebuild.
Rebuild only after changing `requirements.txt`, `package.json`, or a
Dockerfile. Changes to `database/schema.sql` apply only to a fresh volume,
since the init script runs once — see [database.md](database.md) for how to
apply changes to an existing database.
