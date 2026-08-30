# API Reference

Base URL: `http://localhost:8000` (Docker Compose default). All endpoints are
mounted under `/api`, except `/`, `/health`, and static uploads at `/uploads`.

Interactive Swagger docs are served by FastAPI itself at `/docs` whenever the
backend is running.

Authenticated endpoints expect `Authorization: Bearer <token>`, where
`<token>` is the JWT returned by `/api/auth/register` or `/api/auth/login`.

## Conventions

- Request/response bodies are JSON unless noted (item reporting uses
  `multipart/form-data` because it carries file uploads).
- All `*_score` / `*_decay` fields are floats in `[0, 1]`.
- Enum fields (`type`, `category`, `status`, ...) are returned as their string
  value, e.g. `"LOST"`, `"ELECTRONICS"`, `"OPEN"`.
- Timestamps are ISO 8601 with timezone.

---

## Health & meta

### `GET /`
Returns basic service info. No auth.

### `GET /health`
Liveness check that also reports which embedding models are loaded and on
which device, **without** forcing a model load (hitting this endpoint never
triggers a download).

```json
{
  "status": "healthy",
  "embeddings": {
    "enabled": true,
    "device": "cpu",
    "text": { "model": "google/siglip-base-patch16-224", "loaded": false },
    "image": { "model": "facebook/dinov2-base", "loaded": false }
  }
}
```

---

## Authentication — `/api/auth`

### `POST /api/auth/register`
Registers a new account. Auth: none.

**Body**
```json
{ "email": "you@college.edu", "full_name": "Ada Lovelace", "password": "at least 8 chars" }
```

- Email must match the configured `CAMPUS_EMAIL_DOMAIN` (default `college.edu`),
  or the request 400s.
- Duplicate email 400s.
- New accounts are always created with `role = STUDENT`. No endpoint promotes
  a user to `STAFF`; that requires a direct database update (see
  [deployment.md](deployment.md)).

**Response** `TokenResponse` (also returned by `/login`):
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 1, "email": "you@college.edu", "full_name": "Ada Lovelace",
    "role": "STUDENT", "karma_score": 100, "created_at": "2026-08-29T12:00:00Z"
  }
}
```

### `POST /api/auth/login`
**Body**: `{ "email": "...", "password": "..." }`
Returns the same `TokenResponse` shape, or `401` on bad credentials.

### `GET /api/auth/me`
Auth: required. Returns the caller's `UserResponse` (including `karma_score`).

---

## Items — `/api/items`

### `POST /api/items/report`
Report a lost or found item. Auth: required.
Content-Type: `multipart/form-data`.

| Field | Type | Notes |
| --- | --- | --- |
| `type` | string | `LOST` or `FOUND` |
| `title` | string | required |
| `description` | string | required — also mined for OCR-style identifier tokens |
| `category` | string | one of `ELECTRONICS`, `WALLETS_CARDS`, `KEYS`, `CLOTHING`, `DOCUMENTS`, `OTHER` |
| `campus_zone` | string | free text, must match zone names the frontend uses for adjacency to work |
| `incident_time` | string | ISO 8601 datetime |
| `is_high_value` | bool | default `false`; hides photos from non-owners once set |
| `latitude`, `longitude` | float | optional |
| `images` | file[] | 0–3 files; `jpg/jpeg/png/gif/webp/pdf`; each ≤ `MAX_UPLOAD_SIZE` (10 MB default) |

On success (`201`-equivalent `ItemResponse`, returned as `200`):
1. Images are saved to `UPLOAD_DIR` under a generated `{user_id}_{uuid}.{ext}`
   name (never the client-supplied filename) and served back at `/uploads/<name>`.
2. A `text_embedding` is generated from title + description + category + zone.
   If a photo was attached, the first image also produces an `image_embedding`
   and a detected `brand`.
3. Matching runs synchronously against every `OPEN` item of the opposite type
   in the same category — any pair that clears the `POTENTIAL` threshold is
   persisted as a `Match` row before the response is returned (see
   [ai-matching.md](ai-matching.md)). A matching failure is logged and does
   not affect the report response.

### `GET /api/items/feed`
Paginated list of open items. Auth: optional (unauthenticated callers see
masked high-value items; the owner and any authenticated viewer other than
the owner both see the mask applied — only the reporting user sees the real
photos).

Query params: `skip` (default 0), `limit` (default 20), `category`,
`campus_zone`, `type`.

Returns `ItemListResponse[]`.

### `GET /api/items/{item_id}`
Single item detail. Auth: optional. Same high-value masking as the feed.

### `GET /api/items/`
The caller's own items (both lost and found reports). Auth: required.

---

## Matches — `/api/matches`

### `POST /api/matches/find`
Re-run matching for one of your own items. Matching also runs automatically
on `POST /items/report`; use this to refresh matches after new counterpart
items have since been posted. Auth: required — the item must belong to the
caller (`403` otherwise).

**Body**: `{ "item_id": 42 }`

**Response**
```json
{
  "item_id": 42,
  "item_type": "LOST",
  "matches_found": 2,
  "matches": [ { "...": "MatchResponse fields" } ]
}
```

### `GET /api/matches/mine`
Every match touching any item the caller reported, best score first, with
both sides of each match embedded so the UI can render a match card without
a follow-up request per item. Auth: required.

Returns `EnrichedMatchResponse[]` — each entry adds `your_item` and
`matched_item` (both `MatchedItemSummary`) on top of the base `MatchResponse`
fields, from the caller's point of view.

### `GET /api/matches/item/{item_id}`
Matches for one specific item the caller owns, best score first, enriched the
same way as `/mine`. Auth: required; `403` if the item isn't the caller's.

### `GET /api/matches/{match_id}`
Raw match record by id (no enrichment). Auth: required.

**`MatchResponse` fields**: `id`, `lost_item_id`, `found_item_id`,
`visual_score`, `text_score`, `category_score`, `spatial_decay`,
`temporal_decay`, `ocr_bonus`, `total_score`, `status`
(`HIGH_CONFIDENCE` | `POTENTIAL` | `REJECTED` | `VERIFIED`), `created_at`.

---

## Claims — `/api/claims`

The claim flow in this codebase is a two-party ownership challenge, **not**
the QR-handshake flow described in the project's original spec (see the note
at the end of this section).

### `POST /api/claims/challenge/create`
Open a claim on a match: the claimant supplies an ownership question and
their own answer. Auth: required.

**Body**: `{ "match_id": 7, "challenge_question": "...", "claimant_answer": "..." }`

### `POST /api/claims/challenge/respond`
Revise the answer on a claim you opened. Auth: required — must be the
claimant; `403` otherwise. `400` if the claim is already resolved.

**Body**: `{ "claim_id": 3, "answer": "..." }`

### `POST /api/claims/challenge/approve`
Approve the claim and complete the handover in one step. Auth: required —
only the user who reported the matched **found** item may approve
(`403` otherwise). `400` if already resolved.

**Body**: `{ "claim_id": 3 }`

Effects: `claim.is_challenge_approved = true`, `resolved_at` is stamped, both
the lost and found item move to `status = RESOLVED`, and the finder's
`karma_score` is incremented by **25**.

> **Divergence from spec:** `spec.txt` and the top-level README describe a
> cryptographic, time-bound QR handshake (`handshake_qr_token`,
> `POST /handshake/verify`, an admin scan step) as the final handover step.
> That flow is not implemented here — approval by the finder *is* the final
> step. The `Claim` model in this codebase has no `handshake_qr_token` or
> `handover_by_user_id` column.

---

## Admin — `/api/admin`

### `GET /api/admin/stats`
Public system-wide counters used by the landing page. Auth: none — this is
**not** admin-gated in the current implementation, despite the router name.

```json
{
  "total_items": 120,
  "lost_items": 64,
  "found_items": 56,
  "resolved_items": 18,
  "resolution_rate": 15.0
}
```

> **Divergence from spec:** the original spec describes `/api/admin/vault/unclaimed`
> and `/api/admin/vault/process` (45-day unclaimed-item vault) plus a QR scan
> audit endpoint, gated to a `SECURITY_ADMIN` role. None of those exist in this
> codebase — `admin.py` currently defines only `GET /stats`, and there is no
> `SECURITY_ADMIN` role to gate it with.

---

## Error shape

FastAPI's default error body:
```json
{ "detail": "Human-readable message" }
```
Common status codes: `400` (validation / duplicate), `401` (missing/invalid
token), `403` (authenticated but not permitted), `404` (not found), `413`
(file too large).
