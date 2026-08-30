# AI Matching

This document covers how a lost report and a found report get compared and
scored: the two embedding models, the hybrid scoring formula, and the offline
evaluation tooling. Everything here reflects `backend/app/services/*` — the
code that actually runs in the request path — with the standalone `ml/`
workspace noted separately where it has drifted from it.

## 1. Two towers, not one

The original project spec called for a single model (SigLIP) for both images
and text. The implemented backend (`backend/app/services/embeddings.py`)
deliberately uses **two**:

| Job | Model | Why |
| --- | --- | --- |
| Text embedding | SigLIP (`google/siglip-base-patch16-224`) | A caption-aligned space is a good semantic match for two people describing the same object in their own words. |
| Image embedding | DINOv2 (`facebook/dinov2-base`) | Re-identification needs *instance-level* detail. SigLIP is trained to align images with captions, which never mention which specific handset — so it learns to ignore exactly the scuffs and wear that identify one object from another of the same kind. |

This was a measured decision, not a stylistic one: on real uploads, SigLIP
scored two **different** Motorola phones (0.86 cosine similarity) higher than
the **same** iPhone re-photographed (0.68) — the ranking inverted. DINOv2,
being self-supervised with no text supervision, keeps the fine-grained
appearance detail that re-identification depends on and does not make this
mistake.

Both models emit 768-dimensional vectors, so `Item.image_embedding` and
`Item.text_embedding` are both `vector(768)` and share the same column type
regardless of which model produced them (see the note in
[database.md](database.md) about the `2048`→`768` migration history).

Models load **lazily** on first use (not at import), guarded by a lock so a
concurrent request can't trigger a duplicate load. A failed load is latched
(`_load_failed`) so every subsequent request doesn't re-pay the same timeout.
On any failure, an embedder returns `None` rather than a fabricated vector — a
fabricated embedding would still produce a plausible-looking cosine score that
reads as a confident match while meaning nothing.

`EMBEDDINGS_ENABLED=false` skips loading both models entirely; matching still
runs, but the visual and text terms stay at 0 and only category, decay, and
the OCR bonus contribute (which rarely clears the `POTENTIAL` threshold on its
own — useful for a lightweight deploy or a fast test run, not for production
matching quality).

## 2. Image preprocessing: letterbox + object crop

Two preprocessing steps happen before an image reaches DINOv2
(`DINOv2ImageEmbedder` in `embeddings.py`):

1. **Letterbox, not center-crop.** DINOv2's default HuggingFace processor
   resizes the shortest edge to 256px and center-crops to 224px. For a tall
   product photo this throws away most of the object and keeps mostly
   background — measured on real uploads, this made a black Motorola score
   *higher* against an orange iPhone (0.656) than against a blue Motorola
   (0.615), purely because the wrong object's aspect ratio happened to survive
   the crop. The fix pads to a square instead of cropping, which flipped that
   to 0.828 for the correct pair.
2. **Saliency-based object crop** (`OBJECT_CROP=true`, default on). DINOv2's
   own CLS-token attention gives a saliency map for free: patches that align
   with the CLS token are foreground, patches that don't are background. The
   image is cropped to the bounding box of high-saliency patches before
   embedding, so the same item photographed on a desk, on grass, or on tiles
   produces nearly the same vector. Measured separation from the nearest wrong
   object improved from +0.063 → +0.076 (desk), +0.071 → +0.081 (grass), and
   +0.072 → +0.085 (tiles).

## 3. Zero-shot brand detection

`SigLIPTextEmbedder.detect_brand` runs SigLIP's image tower zero-shot against
a fixed vocabulary (`BRAND_VOCABULARY` in `core/config.py` — Apple, Samsung,
Motorola, Nike, JBL, etc.) to read a brand label off the first photo. This is
*not* used for retrieval, only as a mismatch signal: a confident disagreement
("this is a Motorola, that's an Apple") is strong evidence two items are
**not** the same object even if their embeddings look similar. The top
prediction is only accepted if it clears `BRAND_MIN_CONFIDENCE` (0.08) **and**
is at least 2x the runner-up's score; otherwise the brand is recorded as
`None` — and an unknown brand is never treated as a mismatch, only a confident
disagreement is.

## 4. Candidate retrieval

`services/matching.py::find_candidates` is a hard category pre-filter: for a
given item, it queries every `OPEN` item of the opposite type
(`LOST` ↔ `FOUND`) **in the same category**. This is why `category_score` is
always `1.0` for anything that actually reaches scoring — non-matching
categories never get there.

This is a plain SQL `WHERE` query, not a `pgvector` ANN search — the HNSW
indexes on `image_embedding`/`text_embedding` (see [database.md](database.md))
are provisioned in the schema but not yet queried directly. At current data
volumes this is fine; at scale, candidate retrieval would move to a
`pgvector` nearest-neighbor query before falling back to the full scoring
formula for re-ranking.

## 5. OCR-style identifier extraction

`utils/validators.py::extract_ocr_tokens` pulls serial-number-like
identifiers out of free-text descriptions with a regex — it is **not** OCR
run on the photo itself, despite the name (Tesseract is listed as a
dependency but is not called from `services/` or `api/`). The pattern
requires either a run of 4+ alphanumeric characters containing at least one
letter and one digit (`DL992384`, `SERIAL9931`), or a pure-digit run of 6+
(IMEI/receipt fragments).

This is deliberately narrower than an earlier version that matched any
`[A-Za-z0-9]{4,}` token: that version let ordinary words share a token — a
phone described as "black" and an umbrella described as "black" would collect
the full identity bonus for having a colour in common. A serial number is
real evidence of identity; a colour is not.

## 6. The hybrid scoring formula

All scoring logic lives in `backend/app/services/scoring.py::ScoringEngine`.

```
feature_score = w_v * S_visual + w_t * S_text + w_c * S_category
context       = CONTEXT_FLOOR + (1 - CONTEXT_FLOOR) * (D_spatial * D_temporal)
total_score   = min(1, max(0, (feature_score * context + B_ocr) * brand_factor))
```

| Term | Computation |
| --- | --- |
| `S_visual` | Cosine similarity of the two `image_embedding` vectors; `0.0` if either is `None` |
| `S_text` | Cosine similarity of the two `text_embedding` vectors; `0.0` if either is `None` |
| `S_category` | `1.0` on exact category match, `0.0` otherwise (in practice always `1.0` post-filter) |
| `D_spatial` | Haversine-based (`1 / (1 + 0.5 * distance_km)`) if both items have GPS coordinates; otherwise `1.0` same zone / `0.8` adjacent zone / `0.4` distant zone; `0.5` if neither zone nor GPS is comparable |
| `D_temporal` | `exp(-0.05 * days_between)`; `0.1` if the found time precedes the lost time |
| `B_ocr` | `+0.25` flat bonus if the two items share any extracted identifier token, else `0.0` |
| `brand_factor` | `1.0` unless both items have a confidently-detected brand and they disagree, in which case `0.55` |

**Weights** are `w_v=0.45, w_t=0.30, w_c=0.25` when both items have a photo,
rebalancing to `w_v=0, w_t=0.70, w_c=0.30` when either does not.

**Context floor.** Multiplying the feature score by raw `D_spatial * D_temporal`
would make thresholds unreliable: a true match found 7 days later
(`0.90 * 0.705 = 0.63`) could score *below* a same-day false match
(`0.65 * 1.0`). `CONTEXT_FLOOR = 0.65` bounds the context multiplier into
`[0.65, 1.0]`, so location/time can attenuate a score but never veto it —
"right item, found later or elsewhere" stays above "wrong item, found here and
now."

**Brand factor** is applied last, scaling the *entire* score including the OCR
bonus — a shared identifier-like token means nothing if the photos show
products from two different confidently-identified makers.

### Thresholds

```
total_score >= 0.85   -> HIGH_CONFIDENCE
total_score >= 0.70   -> POTENTIAL
total_score <  0.70   -> REJECTED (not persisted)
```

These were calibrated against `backend/scripts/benchmark.py` using real
uploaded photos and graded re-photography: at a naive `0.70` cutoff (before
the context floor was introduced) precision was only 57%; after the context
floor the false-match band tops out around `0.65`, so `0.70` reliably
separates true matches — even across a two-week gap — from same-day false
pairs.

> Note: `spec.txt` and the top-level README describe thresholds of `0.80` /
> `0.55`. The values above (`0.85` / `0.70`) are what's actually implemented
> in `ScoringEngine` in this codebase, and are the ones that govern real
> behavior.

## 7. Where matching is triggered

- **Automatically**, inside `POST /api/items/report` — every new report is
  scored against all open counterparts immediately, synchronously, before the
  response is returned.
- **On demand**, via `POST /api/matches/find` — re-runs matching for one of
  the caller's own items (useful after new counterparts have since been
  posted).

Both call the same `services/matching.py::find_matches_for_item`, which
updates existing `Match` rows in place on re-score (rather than duplicating),
and downgrades — rather than deletes — a match that drops below threshold if
a `Claim` already references it (deleting it would cascade-delete a real
handover record).

## 8. Recomputing embeddings after a model change

`backend/scripts/reembed.py` recomputes every item's `text_embedding`,
`image_embedding`, `ocr_tokens`, and `brand`, then rebuilds all `Match` rows
(clearing stale ones, preserving any that carry a claim). Run this after
changing `SIGLIP_MODEL`/`DINOV2_MODEL`, after a database migration that
touches embedding columns, or after changing `extract_ocr_tokens`:

```bash
docker exec campus-lost-found-backend-1 python scripts/reembed.py
```

Vectors from two different models are not comparable — they share a
dimensionality and nothing else, so mixing them produces a cosine similarity
that looks like a plausible score but is actually noise.

## 9. Offline evaluation

Two separate scripts exercise the *production* `ScoringEngine` against a
small labelled benchmark built from real uploaded photos (four objects, each
represented once in a "found" gallery and once as a re-photographed,
differently-described "lost" query, at three levels of rotation/blur/lighting
distortion):

- `backend/scripts/benchmark.py` — reports ranking accuracy and how the live
  thresholds classify true vs. false pairs.
  ```bash
  docker exec campus-lost-found-backend-1 python scripts/benchmark.py
  ```
- `backend/scripts/tune.py` — sweeps scoring configurations against the same
  benchmark, reporting Recall@1/MRR (ranking quality) and best-achievable F1
  with its threshold (classification quality) per variant.
  ```bash
  docker exec campus-lost-found-backend-1 python scripts/tune.py
  ```

### The `ml/` workspace

`ml/src/` is a **separate, standalone** copy of the matching logic
(`ranking/scorer.py`, `embeddings/siglip_model.py`, `evaluation/`,
`retrieval/vector_search.py`) intended as an offline research/evaluation
harness, run manually — it is not imported by the backend and does not serve
requests. It's driven by `ml/src/evaluation/run_eval.py` against
`ml/data/processed/campus_test_pairs.json`:

```bash
python ml/src/evaluation/run_eval.py --dataset ml/data/processed/campus_test_pairs.json --top_k 5
```

Its scorer (`ml/src/ranking/scorer.py`) does mirror the backend's context-floor
mechanism, but it:
- has **no brand-mismatch factor** (the backend's `brand_factor` term),
- has **no built-in decision thresholds** — it returns a raw score, not a
  `HIGH_CONFIDENCE`/`POTENTIAL`/`REJECTED` label,
- and its companion `ml/src/embeddings/siglip_model.py` / `ml/README.md`
  still describe SigLIP as the model for **both** images and text — they were
  not updated when the backend switched image embedding to DINOv2.

Treat `ml/` as a lagging reference implementation for research purposes, and
`backend/app/services/scoring.py` + `backend/scripts/benchmark.py`/`tune.py`
as the source of truth for how matching actually behaves in production.

`.github/workflows/ml-ci.yml` runs `ml/src/evaluation/run_eval.py` on any push
touching `ml/**` or `backend/app/services/scoring.py`, checking for
`MRR >= 0.75` and `Recall@5 >= 0.85` (informational thresholds printed in the
job log — the workflow does not currently fail the build if they're missed).
