from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.database import get_db
from app.core.config import get_settings
from app.models.item import Item, ItemType, ItemCategory, ItemStatus
from app.schemas.item import ItemCreate, ItemResponse, ItemListResponse
from app.utils.validators import validate_file_extension, extract_ocr_tokens
from app.core.security import get_current_user_id, get_optional_user_id

router = APIRouter()
settings = get_settings()

@router.post("/report", response_model=ItemResponse)
async def report_item(
    type: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    campus_zone: str = Form(...),
    incident_time: str = Form(...),
    is_high_value: bool = Form(False),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    # NOTE: must be a bare List, not Optional[List[...]]. With a Union annotation
    # FastAPI uses form.get() instead of form.getlist(), so sending a single file
    # yields one UploadFile where a list is expected and the request 422s.
    images: List[UploadFile] = File(default=[]),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Report a lost or found item with up to 3 images"""

    # Validate input
    if type not in [e.value for e in ItemType]:
        raise HTTPException(status_code=400, detail=f"Invalid type: {type}")
    
    if category not in [e.value for e in ItemCategory]:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    
    # Process images
    image_urls = []
    # Browsers send an empty part for an empty file input; ignore those
    files = [img for img in (images or []) if img and img.filename]
    if files:
        if len(files) > 3:
            raise HTTPException(status_code=400, detail="A maximum of 3 images is allowed")

        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        for image in files:
            if not validate_file_extension(image.filename):
                raise HTTPException(status_code=400, detail=f"Invalid file type: {image.filename}")

            content = await image.read()
            if len(content) > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"{image.filename} exceeds the {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB limit",
                )

            # Never build a path from the client-supplied filename
            ext = image.filename.rsplit(".", 1)[1].lower()
            filename = f"{user_id}_{uuid4().hex}.{ext}"

            with open(upload_dir / filename, "wb") as f:
                f.write(content)

            image_urls.append(f"/uploads/{filename}")

    # Parse incident time
    try:
        incident_dt = datetime.fromisoformat(incident_time)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid incident_time: {incident_time}")
    
    # Extract OCR tokens from description
    ocr_tokens = extract_ocr_tokens(description)
    
    # Create item
    db_item = Item(
        user_id=user_id,
        type=ItemType[type.upper()],
        title=title,
        description=description,
        category=ItemCategory[category.upper()],
        campus_zone=campus_zone,
        incident_time=incident_dt,
        image_urls=image_urls,
        ocr_tokens=ocr_tokens,
        is_high_value=is_high_value,
        latitude=latitude,
        longitude=longitude
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return ItemResponse.from_orm(db_item)

@router.get("/feed", response_model=List[ItemListResponse])
async def get_feed(
    skip: int = 0,
    limit: int = 20,
    category: Optional[str] = None,
    campus_zone: Optional[str] = None,
    type: Optional[str] = None,
    current_user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db)
):
    """Get paginated feed of open items with masking for sensitive items"""
    
    query = db.query(Item).filter(Item.status == ItemStatus.OPEN)
    
    # Apply filters
    if category:
        query = query.filter(Item.category == category)
    if campus_zone:
        query = query.filter(Item.campus_zone == campus_zone)
    if type:
        query = query.filter(Item.type == type)
    
    items = query.order_by(Item.created_at.desc()).offset(skip).limit(limit).all()
    
    # Mask high-value items for non-owners. Mask the response object, never the
    # ORM row, or a later flush would erase the URLs from the database.
    results = []
    for item in items:
        data = ItemListResponse.from_orm(item)
        if item.is_high_value and item.user_id != current_user_id:
            data.image_urls = []
        results.append(data)

    return results

@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    current_user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db)
):
    """Get single item details"""

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    data = ItemResponse.from_orm(item)
    # Same masking as the feed, or this endpoint becomes a way around it
    if item.is_high_value and item.user_id != current_user_id:
        data.image_urls = []
    return data

@router.get("/", response_model=List[ItemResponse])
async def get_user_items(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get user's items"""

    items = db.query(Item).filter(Item.user_id == user_id).all()
    return [ItemResponse.from_orm(item) for item in items]
