from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ItemBase(BaseModel):
    title: str
    description: str
    category: str
    campus_zone: str
    incident_time: datetime
    is_high_value: bool = False

class ItemCreate(ItemBase):
    type: str

class ItemResponse(ItemBase):
    id: int
    user_id: int
    type: str
    image_urls: List[str] = []
    ocr_tokens: List[str] = []
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ItemListResponse(BaseModel):
    id: int
    title: str
    category: str
    campus_zone: str
    type: str
    is_high_value: bool
    image_urls: List[str] = []
    created_at: datetime
    
    class Config:
        from_attributes = True
