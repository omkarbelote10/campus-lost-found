from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.item import Item, ItemType, ItemStatus
from app.models.match import Match, MatchStatus, Claim
from app.schemas.match import MatchResponse, ClaimCreate, ClaimResponse, QRHandshakeResponse, FindMatchesRequest
from app.services.scoring import ScoringEngine
from app.core.security import create_qr_token, get_current_user_id

router = APIRouter()

@router.post("/find")
async def find_matches(
    request: FindMatchesRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Find matching items for a lost item"""

    lost_item_id = request.lost_item_id
    lost_item = db.query(Item).filter(Item.id == lost_item_id).first()
    if not lost_item or lost_item.type != ItemType.LOST:
        raise HTTPException(status_code=404, detail="Lost item not found")

    if lost_item.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only find matches for your own items")

    # Get all found items of same category
    found_items = db.query(Item).filter(
        Item.type == ItemType.FOUND,
        Item.category == lost_item.category,
        Item.status == ItemStatus.OPEN
    ).all()
    
    matches = []
    
    for found_item in found_items:
        # Calculate scores
        visual_score = ScoringEngine.calculate_visual_score(
            lost_item.image_embedding, 
            found_item.image_embedding
        )
        
        text_score = ScoringEngine.calculate_text_score(
            lost_item.text_embedding,
            found_item.text_embedding
        )
        
        category_score = ScoringEngine.calculate_category_score(
            lost_item.category, 
            found_item.category
        )
        
        spatial_decay = ScoringEngine.calculate_spatial_decay(
            lost_item.latitude, lost_item.longitude,
            found_item.latitude, found_item.longitude,
            lost_item.campus_zone, found_item.campus_zone
        )
        
        temporal_decay = ScoringEngine.calculate_temporal_decay(
            lost_item.incident_time,
            found_item.incident_time
        )
        
        ocr_bonus = ScoringEngine.calculate_ocr_bonus(
            lost_item.ocr_tokens,
            found_item.ocr_tokens
        )
        
        # Calculate total score
        total_score, match_status = ScoringEngine.calculate_total_score(
            visual_score, text_score, category_score,
            spatial_decay, temporal_decay, ocr_bonus,
            has_image_1=bool(lost_item.image_urls),
            has_image_2=bool(found_item.image_urls)
        )
        
        # Only save if meets threshold
        if match_status != "REJECTED":
            match = Match(
                lost_item_id=lost_item_id,
                found_item_id=found_item.id,
                visual_score=visual_score,
                text_score=text_score,
                category_score=category_score,
                spatial_decay=spatial_decay,
                temporal_decay=temporal_decay,
                ocr_bonus=ocr_bonus,
                total_score=total_score,
                status=MatchStatus[match_status]
            )
            
            db.add(match)
            matches.append(match)
    
    db.commit()
    
    return {
        "lost_item_id": lost_item_id,
        "matches_found": len(matches),
        "matches": [MatchResponse.from_orm(m) for m in matches]
    }

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

@router.get("/item/{item_id}", response_model=List[MatchResponse])
async def get_item_matches(
    item_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get all matches for an item"""

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your item")

    matches = db.query(Match).filter(
        (Match.lost_item_id == item_id) | (Match.found_item_id == item_id)
    ).all()
    
    return [MatchResponse.from_orm(m) for m in matches]
