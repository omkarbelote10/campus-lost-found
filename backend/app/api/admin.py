from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from app.core.database import get_db
from app.core.security import require_admin
from app.models.item import Item, ItemStatus
from app.schemas.item import ItemResponse

router = APIRouter()

class VaultProcessRequest(BaseModel):
    action: str  # "donation" or "auction"

@router.get("/vault/unclaimed", response_model=List[ItemResponse])
async def get_unclaimed_items(
    admin_id: int = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get items older than 45 days (unclaimed)"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=45)
    
    items = db.query(Item).filter(
        Item.status == ItemStatus.OPEN,
        Item.created_at < cutoff_date
    ).all()
    
    return [ItemResponse.from_orm(item) for item in items]

@router.post("/vault/process")
async def process_vault_items(
    request: VaultProcessRequest,
    admin_id: int = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Bulk process unclaimed items"""

    action = request.action
    if action not in ("donation", "auction"):
        raise HTTPException(status_code=400, detail="action must be 'donation' or 'auction'")

    cutoff_date = datetime.utcnow() - timedelta(days=45)
    
    items = db.query(Item).filter(
        Item.status == ItemStatus.OPEN,
        Item.created_at < cutoff_date
    ).all()
    
    for item in items:
        item.status = ItemStatus.UNCLAIMED_VAULT
    
    db.commit()
    
    return {
        "message": f"Processed {len(items)} items",
        "action": action,
        "count": len(items)
    }

@router.get("/qr-scans")
async def get_recent_scans(
    admin_id: int = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get recent QR handshake scans for audit"""
    
    from app.models.match import Claim
    
    # Get recent resolved claims
    claims = db.query(Claim).filter(
        Claim.resolved_at != None
    ).order_by(Claim.resolved_at.desc()).limit(50).all()
    
    return {
        "recent_scans": len(claims),
        "scans": [
            {
                "claim_id": claim.id,
                "resolved_at": claim.resolved_at,
                "handover_by": claim.handover_by_user_id
            } for claim in claims
        ]
    }

@router.get("/stats")
async def get_system_stats(db: Session = Depends(get_db)):
    """Get system statistics"""
    
    total_items = db.query(Item).count()
    lost_items = db.query(Item).filter(Item.type == "LOST").count()
    found_items = db.query(Item).filter(Item.type == "FOUND").count()
    resolved = db.query(Item).filter(Item.status == ItemStatus.RESOLVED).count()
    
    return {
        "total_items": total_items,
        "lost_items": lost_items,
        "found_items": found_items,
        "resolved_items": resolved,
        "resolution_rate": round((resolved / total_items * 100) if total_items > 0 else 0, 2)
    }
