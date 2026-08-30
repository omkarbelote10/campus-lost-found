"""Candidate retrieval and match persistence.

Shared by POST /items/report (which runs matching automatically for every new
report) and POST /matches/find (which re-runs it on demand). Both directions are
supported: a LOST report is scored against open FOUND items, and a FOUND report
against open LOST items.
"""

from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.item import Item, ItemStatus, ItemType
from app.models.match import Claim, Match, MatchStatus
from app.services.scoring import ScoringEngine


def _ordered_pair(item: Item, candidate: Item) -> Tuple[Item, Item]:
    """Matches are stored lost-first regardless of which side was reported."""
    return (item, candidate) if item.type == ItemType.LOST else (candidate, item)


def find_candidates(db: Session, item: Item) -> List[Item]:
    """Open items of the opposite type in the same category.

    Category is a hard pre-filter, which is why category_score is always 1.0 for
    anything that reaches scoring.
    """
    counterpart = ItemType.FOUND if item.type == ItemType.LOST else ItemType.LOST

    return (
        db.query(Item)
        .filter(
            Item.type == counterpart,
            Item.category == item.category,
            Item.status == ItemStatus.OPEN,
            Item.id != item.id,
        )
        .all()
    )


def score_pair(lost_item: Item, found_item: Item) -> Tuple[dict, float, str]:
    """Run the hybrid formula over one lost/found pair."""
    visual_score = ScoringEngine.calculate_visual_score(
        lost_item.image_embedding, found_item.image_embedding
    )
    text_score = ScoringEngine.calculate_text_score(
        lost_item.text_embedding, found_item.text_embedding
    )
    category_score = ScoringEngine.calculate_category_score(
        lost_item.category, found_item.category
    )
    spatial_decay = ScoringEngine.calculate_spatial_decay(
        lost_item.latitude,
        lost_item.longitude,
        found_item.latitude,
        found_item.longitude,
        lost_item.campus_zone,
        found_item.campus_zone,
    )
    temporal_decay = ScoringEngine.calculate_temporal_decay(
        lost_item.incident_time, found_item.incident_time
    )
    ocr_bonus = ScoringEngine.calculate_ocr_bonus(
        lost_item.ocr_tokens, found_item.ocr_tokens
    )

    brand_factor = ScoringEngine.calculate_brand_factor(
        getattr(lost_item, "brand", None), getattr(found_item, "brand", None)
    )

    total_score, status = ScoringEngine.calculate_total_score(
        visual_score,
        text_score,
        category_score,
        spatial_decay,
        temporal_decay,
        ocr_bonus,
        has_image_1=bool(lost_item.image_urls),
        has_image_2=bool(found_item.image_urls),
        brand_factor=brand_factor,
    )

    components = {
        "visual_score": visual_score,
        "text_score": text_score,
        "category_score": category_score,
        "spatial_decay": spatial_decay,
        "temporal_decay": temporal_decay,
        "ocr_bonus": ocr_bonus,
    }
    return components, total_score, status


def find_matches_for_item(db: Session, item: Item) -> List[Match]:
    """Score `item` against every open counterpart and persist the ones that
    clear the POTENTIAL threshold.

    Re-running this for the same item updates existing rows in place rather than
    inserting duplicates, so the automatic pass on report and a later manual
    /matches/find call cannot stack up rows for the same pair.

    The caller owns the transaction; this function flushes but does not commit.
    """
    candidates = find_candidates(db, item)
    if not candidates:
        return []

    results: List[Match] = []

    for candidate in candidates:
        lost_item, found_item = _ordered_pair(item, candidate)
        components, total_score, status = score_pair(lost_item, found_item)

        existing = (
            db.query(Match)
            .filter(
                Match.lost_item_id == lost_item.id,
                Match.found_item_id == found_item.id,
            )
            .first()
        )

        if status == "REJECTED":
            # A pair that no longer clears the bar should not linger from an
            # earlier run with different data -- but claims cascade-delete with
            # their match, so a re-score would silently erase a real handover
            # record. Downgrade those instead of deleting them.
            if existing:
                if db.query(Claim).filter(Claim.match_id == existing.id).count():
                    existing.status = MatchStatus.REJECTED
                    existing.total_score = total_score
                    for field, value in components.items():
                        setattr(existing, field, value)
                else:
                    db.delete(existing)
            continue

        if existing:
            for field, value in components.items():
                setattr(existing, field, value)
            existing.total_score = total_score
            existing.status = MatchStatus[status]
            results.append(existing)
        else:
            match = Match(
                lost_item_id=lost_item.id,
                found_item_id=found_item.id,
                total_score=total_score,
                status=MatchStatus[status],
                **components,
            )
            db.add(match)
            results.append(match)

    db.flush()
    results.sort(key=lambda m: m.total_score, reverse=True)
    return results
