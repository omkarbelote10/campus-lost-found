from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.item import Item, ItemStatus

router = APIRouter()


@router.get("/stats")
async def get_system_stats(db: Session = Depends(get_db)):
    """Public system statistics, used by the landing page counters."""

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
