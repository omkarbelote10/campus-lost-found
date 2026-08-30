-- Restore items.image_embedding to 768-d, matching the stock DINOv2 tower that
-- app/services/embeddings.py actually uses.
--
-- Why this is needed: the column had been widened to vector(2048) for a locally
-- trained ResNet-50 tower. The application code for that tower was later removed
-- from the working tree, but the database change stayed, leaving the two out of
-- step -- DINOv2 emits 768-d into a 2048-d column, so every report carrying a
-- photo died on INSERT with "expected 2048 dimensions, not 768". In the browser
-- that appears as a CORS error, because an unhandled 500 never passes back
-- through the CORS middleware.
--
--   docker compose exec -T postgres psql -U postgres -d clfis_db \
--     < database/migrations/003_restore_768_image_embedding.sql
--
-- AFTER running this, repopulate the column -- it is left empty and until then
-- every pair scores 0.0 on the visual term:
--
--   docker compose exec backend python scripts/reembed.py

BEGIN;

-- The stored vectors are ResNet-50 outputs. They are not comparable with DINOv2
-- vectors and have no meaningful 768-d cast, so they are cleared rather than
-- converted: an empty column scores 0.0 on the visual term, which is honest,
-- where a retained vector would produce a confident-looking score built on noise.
UPDATE items SET image_embedding = NULL;

ALTER TABLE items ALTER COLUMN image_embedding TYPE vector(768);

-- Recreate the index schema.sql declares. It had to be dropped at 2048-d because
-- pgvector caps HNSW at 2000 dimensions; 768 is comfortably inside that.
CREATE INDEX IF NOT EXISTS idx_items_image_embedding
    ON items USING hnsw (image_embedding vector_cosine_ops);

COMMIT;
