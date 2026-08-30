# Database

PostgreSQL 16, built from `database/Dockerfile` (`postgis/postgis:16-3.4` base
with `postgresql-16-pgvector` installed). Two extensions are required:

```sql
CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector: embedding columns + HNSW ANN search
CREATE EXTENSION IF NOT EXISTS postgis;  -- available for geospatial queries; not
                                          -- currently queried directly by the app,
                                          -- which uses plain latitude/longitude floats
                                          -- and a Haversine formula in Python instead
```

`database/schema.sql` is mounted into the Postgres container's
`/docker-entrypoint-initdb.d/` and runs **once**, on first container init
against an empty volume. It is the source of truth for a fresh database; it
is not re-applied to an existing volume on restart or rebuild. The
SQLAlchemy models under `backend/app/models/` are a second definition of the
same tables (`Base.metadata.create_all` adds any table that's missing at
backend startup, but does not alter an existing table) — keep the two in sync
by hand when you add a column.

## Enums

```sql
CREATE TYPE user_role AS ENUM ('STUDENT', 'STAFF');
CREATE TYPE item_type AS ENUM ('LOST', 'FOUND');
CREATE TYPE item_category AS ENUM ('ELECTRONICS', 'WALLETS_CARDS', 'KEYS', 'CLOTHING', 'DOCUMENTS', 'OTHER');
CREATE TYPE item_status AS ENUM ('OPEN', 'MATCH_PENDING', 'HANDOVER_SCHEDULED', 'RESOLVED', 'UNCLAIMED_VAULT');
CREATE TYPE match_status AS ENUM ('HIGH_CONFIDENCE', 'POTENTIAL', 'REJECTED', 'VERIFIED');
```

`user_role` has only `STUDENT` and `STAFF` — there is no `SECURITY_ADMIN`
value in this schema (see [architecture.md](architecture.md) §5). Of the five
`item_status` values, application code only ever sets `OPEN` and `RESOLVED`;
`MATCH_PENDING`, `HANDOVER_SCHEDULED`, and `UNCLAIMED_VAULT` are defined but
unused.

## Tables

### `users`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | SERIAL PK | |
| `email` | VARCHAR(255) UNIQUE NOT NULL | validated against `CAMPUS_EMAIL_DOMAIN` at the API layer |
| `hashed_password` | VARCHAR(255) NOT NULL | bcrypt |
| `full_name` | VARCHAR(100) NOT NULL | |
| `phone_number` | VARCHAR(20) | nullable |
| `role` | user_role | default `STUDENT` |
| `karma_score` | INTEGER | default `100`; `+25` on each successfully approved claim as the finder |
| `created_at`, `updated_at` | TIMESTAMPTZ | default `NOW()` |

Indexes: `idx_users_email`, `idx_users_role`.

### `items`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | SERIAL PK | |
| `user_id` | INTEGER FK -> users(id) ON DELETE CASCADE | NOT NULL |
| `type` | item_type NOT NULL | `LOST` or `FOUND` |
| `title` | VARCHAR(150) NOT NULL | |
| `description` | TEXT NOT NULL | source text for the text embedding and OCR-token extraction |
| `category` | item_category NOT NULL | hard pre-filter for candidate matching |
| `campus_zone` | VARCHAR(100) NOT NULL | free text; must match the zone names the scoring engine's adjacency map expects |
| `latitude`, `longitude` | FLOAT | nullable; when both items in a pair have coordinates, spatial decay uses Haversine distance instead of zone adjacency |
| `incident_time` | TIMESTAMPTZ NOT NULL | drives temporal decay |
| `image_urls` | TEXT[] | default `{}`; up to 3 `/uploads/...` paths |
| `image_embedding` | `vector(768)` | nullable; DINOv2 output — see note below |
| `text_embedding` | `vector(768)` | nullable; SigLIP text-tower output |
| `ocr_tokens` | TEXT[] | default `{}`; serial/ID-like identifiers mined from `description` |
| `brand` | VARCHAR(50) | nullable; zero-shot brand label read off the first photo |
| `is_high_value` | BOOLEAN | default `false`; hides `image_urls` from non-owners at the API layer |
| `private_details` | TEXT | nullable; ground-truth detail for claim verification, never returned in list/detail responses |
| `status` | item_status | default `OPEN` |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

Indexes: `type`, `category`, `user_id`, `status`, `incident_time` (B-tree), plus
two HNSW ANN indexes:
```sql
CREATE INDEX idx_items_image_embedding ON items USING hnsw (image_embedding vector_cosine_ops);
CREATE INDEX idx_items_text_embedding  ON items USING hnsw (text_embedding vector_cosine_ops);
```
In practice the application does not issue ANN queries against these indexes
today — `services/matching.py` retrieves *all* open counterparts in the same
category with a plain SQL filter and scores them one by one in Python. The
HNSW indexes are provisioned for when candidate retrieval is scaled to use
`pgvector`'s nearest-neighbor search directly (see [ai-matching.md](ai-matching.md) §4).

> **Embedding dimensionality history:** both embedding columns are `vector(768)`.
> `database/migrations/003_restore_768_image_embedding.sql` documents that
> `image_embedding` was previously widened to `vector(2048)` for a locally
> trained ResNet-50 tower that was later removed from the codebase, leaving
> the column out of step with the DINOv2 tower (`facebook/dinov2-base`, 768-d)
> that `services/embeddings.py` actually uses. Symptom: every report carrying
> a photo failed on `INSERT` with a dimension mismatch, which surfaced in the
> browser as an opaque CORS error (an unhandled 500 never passes back through
   the CORS middleware). See the migration file and [deployment.md](deployment.md)
> for how to apply it and re-embed existing rows.

### `matches`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | SERIAL PK | |
| `lost_item_id` | INTEGER FK -> items(id) ON DELETE CASCADE | |
| `found_item_id` | INTEGER FK -> items(id) ON DELETE CASCADE | |
| `visual_score`, `text_score`, `category_score`, `spatial_decay`, `temporal_decay`, `ocr_bonus` | FLOAT NOT NULL | individual terms of the hybrid formula, see [ai-matching.md](ai-matching.md) |
| `total_score` | FLOAT NOT NULL | final blended score in `[0, 1]` |
| `status` | match_status NOT NULL | `HIGH_CONFIDENCE`, `POTENTIAL`, or `REJECTED` on write; `VERIFIED` is defined but not currently set by any code path |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

Indexes: `lost_item_id`, `found_item_id`, `total_score`, `status`.

One row exists per (lost item, found item) pair that has ever cleared the
`POTENTIAL` threshold. Re-scoring updates the row in place rather than
inserting a duplicate. A pair that drops below threshold on a re-score is
deleted outright — *unless* a `Claim` already references it, in which case the
row is downgraded to `REJECTED` in place rather than deleted, since deleting it
would cascade-delete a real claim/handover record.

### `claims`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | SERIAL PK | |
| `match_id` | INTEGER FK -> matches(id) ON DELETE CASCADE | |
| `claimant_id` | INTEGER FK -> users(id) ON DELETE CASCADE | |
| `challenge_question` | TEXT NOT NULL | |
| `claimant_answer` | TEXT NOT NULL | |
| `is_challenge_approved` | BOOLEAN | default `false` |
| `resolved_at` | TIMESTAMPTZ | nullable; set on approval |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

Indexes: `match_id`, `claimant_id`.

There is **no** `handshake_qr_token` or `handover_by_user_id` column in this
table, despite both being described in `spec.txt`/README — the implemented
claim flow ends at `challenge/approve`, not a QR handshake (see
[api.md](api.md) for the claim endpoints).

## Migrations

There is no Alembic (or other) migration framework wired up despite
`alembic` being listed in `backend/requirements.txt` — schema changes are
tracked as hand-written, hand-applied SQL files under `database/migrations/`.
Apply one against a running database with:

```bash
docker compose exec -T postgres psql -U postgres -d clfis_db \
  < database/migrations/003_restore_768_image_embedding.sql
```

After a migration that touches embedding columns, repopulate them and rebuild
matches with `backend/scripts/reembed.py` (see [deployment.md](deployment.md)
and [ai-matching.md](ai-matching.md)).

## Resetting a local database

```bash
docker compose down
docker volume rm lost_found_postgres_data
docker compose up -d --build
```

This permanently deletes local data and re-runs `schema.sql` from scratch —
useful when developing schema changes, since `schema.sql` itself is only
applied once per volume.
