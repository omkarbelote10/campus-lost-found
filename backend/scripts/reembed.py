"""Recompute every item's embeddings, then rebuild all matches.

Run this whenever an embedding model changes. Vectors from two different models
are not comparable -- a SigLIP image vector and a DINOv2 image vector share a
dimensionality and nothing else, so cosine between them is noise that still looks
like a plausible score. Mixing them is silently wrong, not loudly broken.

    docker exec campus-lost-found-backend-1 python scripts/reembed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.item import Item  # noqa: E402
from app.models.match import Claim, Match  # noqa: E402
# Imported for its side effect: without the users table registered on Base,
# resolving items.user_id raises NoReferencedTableError.
from app.models.user import User  # noqa: E402,F401
from app.services.embeddings import build_item_text, get_embedder  # noqa: E402
from app.services.matching import find_matches_for_item  # noqa: E402
from app.utils.validators import extract_ocr_tokens  # noqa: E402

settings = get_settings()


def local_path_for(image_url: str) -> Path:
    """Map a stored "/uploads/<name>" URL back to the file on disk."""
    return Path(settings.UPLOAD_DIR) / Path(image_url).name


def main() -> int:
    db = SessionLocal()
    embedder = get_embedder()

    items = db.query(Item).order_by(Item.id).all()
    print(f"re-embedding {len(items)} item(s)\n")

    text_ok = image_ok = image_missing = 0

    for item in items:
        text = build_item_text(
            item.title,
            item.description,
            item.category.value if hasattr(item.category, "value") else str(item.category),
            item.campus_zone,
        )
        item.text_embedding = embedder.embed_text(text)
        text_ok += item.text_embedding is not None

        # Also refresh derived tokens: the identifier extractor has changed too,
        # and stale word-tokens would keep granting the OCR identity bonus.
        item.ocr_tokens = extract_ocr_tokens(item.description)

        item.image_embedding = None
        item.brand = None
        if item.image_urls:
            path = local_path_for(item.image_urls[0])
            if path.exists():
                item.image_embedding = embedder.embed_image(str(path))
                item.brand = embedder.detect_brand(str(path))
                image_ok += item.image_embedding is not None
            else:
                image_missing += 1
                print(f"  item {item.id}: image file missing at {path}")

        print(
            f"  item {item.id:>3} {item.type.value:<5} "
            f"text={'ok' if item.text_embedding else '--'} "
            f"image={'ok' if item.image_embedding else '--'} "
            f"brand={(item.brand or '-'):<9} {item.title[:32]}"
        )

    db.commit()
    print(f"\nembeddings: text {text_ok}/{len(items)}, image {image_ok}, missing files {image_missing}")

    # Old rows were scored against the previous model, so rebuild rather than
    # update: a stale score is worse than no score. Matches carrying a claim are
    # left alone -- claims cascade-delete with their match, and a re-score must
    # not erase a handover record. find_matches_for_item re-scores those in place.
    claimed_match_ids = {row[0] for row in db.query(Claim.match_id).distinct().all()}
    stale = db.query(Match).filter(~Match.id.in_(claimed_match_ids or [-1])).all()
    for match in stale:
        db.delete(match)
    db.commit()
    print(f"cleared {len(stale)} stale match row(s); kept {len(claimed_match_ids)} with claims")

    total = 0
    for item in items:
        total += len(find_matches_for_item(db, item))
        db.commit()

    remaining = db.query(Match).count()
    print(f"rebuilt matches: {remaining} row(s)")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
