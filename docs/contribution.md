# Contributing

## Project layout at a glance

- `backend/` — FastAPI service (Python 3.11)
- `frontend/` — Next.js 14 App Router app (TypeScript)
- `database/` — schema + Postgres image
- `ml/` — standalone offline evaluation workspace (not part of the running stack)
- `docs/` — this documentation

See [architecture.md](architecture.md) for what lives where in more detail,
and its "Where to make a given change" table for a quick file lookup.

## Local setup

Use Docker Compose for the full stack — see [deployment.md](deployment.md).
Both `backend` and `frontend` containers hot-reload on source changes, so a
rebuild is only needed after touching `requirements.txt`, `package.json`, or
a Dockerfile.

## Backend

### Style / structure conventions to follow

- Business logic belongs in `app/services/`, not in the route handlers in
  `app/api/`. Route handlers should validate input, call a service, and shape
  the response.
- The SQLAlchemy model (`app/models/`) and `database/schema.sql` are two
  independent definitions of the same tables — a schema change needs both
  files updated, plus a migration file under `database/migrations/` if it
  must be applied to an existing database (see [database.md](database.md)).
- Prefer failing loud in the log over failing silently. Several places in
  this codebase deliberately catch broad exceptions and log with
  `logger.exception(...)` rather than let a secondary failure (e.g. automatic
  matching after a report) take down a primary one (the report itself) — keep
  that pattern rather than swallowing errors silently.
- Never build an upload path from a client-supplied filename — see
  `report_item` in `api/items.py` for the pattern (generated
  `{user_id}_{uuid}.{ext}` name).

### Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/
```

Tests run against a temporary SQLite database (see `tests/conftest.py`), so no
Docker or Postgres is required. Test files: `test_auth.py`, `test_items.py`,
`test_matches_claims_admin.py`, with shared fixtures/utilities in
`conftest.py` and `helpers.py`.

### Backend CI (`.github/workflows/backend-ci.yml`)

Triggered on push/PR touching `backend/**`. Runs, against a real
`postgis/postgis:16-3.4` service container:
- `flake8` (restricted to `E9,F63,F7,F82` — syntax errors and undefined
  names; broader lint rules are not enforced)
- `black --check` (currently non-blocking — the step is suffixed `|| true`)
- `mypy` (also currently non-blocking)
- `pytest tests/ -v` (this one **does** block merge on failure)

## Frontend

```bash
cd frontend
npm install
npm run dev          # dev server
npm run type-check   # tsc --noEmit
npm run build         # production build
npm run lint          # next lint
```

### Frontend CI (`.github/workflows/frontend-ci.yml`)

Triggered on push/PR touching `frontend/**`. Runs `npm ci`, ESLint
(non-blocking, `|| true`), `type-check` (blocking), and `build` (blocking).

## ML / matching changes

If you change anything in `backend/app/services/scoring.py` or
`backend/app/services/embeddings.py`:

1. Run the production benchmark and tuner locally to see the effect on
   real-photo accuracy before opening a PR:
   ```bash
   docker exec campus-lost-found-backend-1 python scripts/benchmark.py
   docker exec campus-lost-found-backend-1 python scripts/tune.py
   ```
2. If the change alters what embeddings look like (a different model, a
   different preprocessing step), existing rows are now scored against stale
   vectors — run `scripts/reembed.py` against any database you're testing
   against.
3. Be aware that `ml/src/` is a **separate**, not-automatically-synced copy of
   the scoring logic used for the `ml-ci.yml` workflow and offline research —
   see [ai-matching.md](ai-matching.md) §9 for how it's currently out of sync
   with the backend (no brand factor, still describes SigLIP for images). If
   your change should also apply there, update `ml/src/ranking/scorer.py` and
   `ml/src/embeddings/` by hand; nothing keeps them in sync automatically.

### ML CI (`.github/workflows/ml-ci.yml`)

Triggered on push/PR touching `ml/**` **or** `backend/app/services/scoring.py`.
Installs `ml/requirements-ml.txt` and runs
`ml/src/evaluation/run_eval.py --dataset ml/data/processed/campus_test_pairs.json --top_k 5`.
The workflow prints the target thresholds (`MRR >= 0.75`, `Recall@5 >= 0.85`)
but does not currently assert them as a hard gate.

## Commit / PR expectations

This repository does not include a `CODEOWNERS`, `CONTRIBUTING` template, or
PR template beyond what's described here. When opening a change:

- Keep backend/frontend/ml changes in separate, focused commits where
  practical — the three CI workflows are path-scoped and only run for the
  areas you touched.
- If you touch a table (`app/models/`), update `database/schema.sql` in the
  same PR and add a migration file if the change needs to run against
  existing data.
- If you touch the scoring formula or a threshold, mention the before/after
  numbers from `scripts/benchmark.py` in the PR description — that's the
  actual evidence used to calibrate the current thresholds (see
  [ai-matching.md](ai-matching.md) §6).
- Update the relevant file in `docs/` alongside the code change where the
  two would otherwise drift — this codebase already has several places where
  `spec.txt`/`README.md` describe behavior (a `SECURITY_ADMIN` role, a QR
  handshake, an unclaimed-item vault, `ml/`'s SigLIP-only pipeline) that
  doesn't match what's actually implemented; try not to add to that list.
