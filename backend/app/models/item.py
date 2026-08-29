from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Boolean, ARRAY, Float, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
from pgvector.sqlalchemy import Vector
import enum

class ItemType(str, enum.Enum):
    LOST = "LOST"
    FOUND = "FOUND"

class ItemCategory(str, enum.Enum):
    ELECTRONICS = "ELECTRONICS"
    WALLETS_CARDS = "WALLETS_CARDS"
    KEYS = "KEYS"
    CLOTHING = "CLOTHING"
    DOCUMENTS = "DOCUMENTS"
    OTHER = "OTHER"

class ItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    MATCH_PENDING = "MATCH_PENDING"
    HANDOVER_SCHEDULED = "HANDOVER_SCHEDULED"
    RESOLVED = "RESOLVED"
    UNCLAIMED_VAULT = "UNCLAIMED_VAULT"

class Item(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(ItemType), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Enum(ItemCategory), nullable=False)
    campus_zone = Column(String(100), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    incident_time = Column(DateTime(timezone=True), nullable=False, index=True)
    image_urls = Column(ARRAY(String(500)), default=[])
    image_embedding = Column(Vector(768))
    text_embedding = Column(Vector(768))
    ocr_tokens = Column(ARRAY(String), default=[])
    is_high_value = Column(Boolean, default=False)
    private_details = Column(Text)
    status = Column(Enum(ItemStatus), default=ItemStatus.OPEN, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
