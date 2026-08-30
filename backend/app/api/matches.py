from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List

from app.core.database import get_db
from app.models.item import Item
from app.models.match import Match
from app.schemas.match import (
    EnrichedMatchResponse,
    FindMatchesRequest,
    MatchedItemSummary,
    MatchResponse,
)
from app.services.matching import find_matches_for_item
from app.core.security import get_current_user_id

router = APIRouter()


def _enrich(match: Match, items_by_id: Dict[int, Item], viewer_item_ids: set) -> EnrichedMatchResponse:
    """Present a match from the viewer's side: `your_item` is whichever end they own."""
    lost = items_by_id[match.lost_item_id]
    found = items_by_id[match.found_item_id]
    mine, theirs = (lost, found) if lost.id in viewer_item_ids else (found, lost)

    return EnrichedMatchResponse(
        **MatchResponse.from_orm(match).dict(),
        your_item=MatchedItemSummary.from_orm(mine),
        matched_item=MatchedItemSummary.from_orm(theirs),
    )


@router.post("/find")
async def find_matches(
    request: FindMatchesRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Re-run matching for one of your items.

    Matching also runs automatically when an item is reported; this endpoint is
    for refreshing an item's matches after new counterparts have been posted.
    Works for both LOST and FOUND items.
    """
    item = db.query(Item).filter(Item.id == request.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only find matches for your own items")

    matches = find_matches_for_item(db, item)
    db.commit()

    return {
        "item_id": item.id,
        "item_type": item.type.value if hasattr(item.type, "value") else str(item.type),
        "matches_found": len(matches),
        "matches": [MatchResponse.from_orm(m) for m in matches],
    }


@router.get("/mine", response_model=List[EnrichedMatchResponse])
async def get_my_matches(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Every match touching an item the caller reported, best score first.

    Declared before /{match_id} so that "mine" is not parsed as a match id.
    """
    my_items = db.query(Item).filter(Item.user_id == user_id).all()
    my_item_ids = {item.id for item in my_items}
    if not my_item_ids:
        return []

    matches = (
        db.query(Match)
        .filter(
            (Match.lost_item_id.in_(my_item_ids)) | (Match.found_item_id.in_(my_item_ids))
        )
        .order_by(Match.total_score.desc())
        .all()
    )
    if not matches:
        return []

    # One query for every counterpart item rather than two lookups per match.
    needed_ids = {m.lost_item_id for m in matches} | {m.found_item_id for m in matches}
    items_by_id = {
        item.id: item for item in db.query(Item).filter(Item.id.in_(needed_ids)).all()
    }

    enriched = []
    for match in matches:
        if match.lost_item_id in items_by_id and match.found_item_id in items_by_id:
            enriched.append(_enrich(match, items_by_id, my_item_ids))
    return enriched


@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get match details"""

    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    return MatchResponse.from_orm(match)


@router.get("/item/{item_id}", response_model=List[EnrichedMatchResponse])
async def get_item_matches(
    item_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Matches for one item, best score first, with both sides embedded.

    Enriched so the report confirmation screen can render match cards straight
    after submitting, without a second round trip per counterpart.
    """
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your item")

    matches = db.query(Match).filter(
        (Match.lost_item_id == item_id) | (Match.found_item_id == item_id)
    ).order_by(Match.total_score.desc()).all()
    if not matches:
        return []

    needed_ids = {m.lost_item_id for m in matches} | {m.found_item_id for m in matches}
    items_by_id = {
        row.id: row for row in db.query(Item).filter(Item.id.in_(needed_ids)).all()
    }

    return [
        _enrich(m, items_by_id, {item_id})
        for m in matches
        if m.lost_item_id in items_by_id and m.found_item_id in items_by_id
    ]
