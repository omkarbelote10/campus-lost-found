from sqlalchemy import Column, Integer, String, DateTime, Enum, Float, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class MatchStatus(str, enum.Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    POTENTIAL = "POTENTIAL"
    REJECTED = "REJECTED"
    VERIFIED = "VERIFIED"

class Match(Base):
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    lost_item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    found_item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    visual_score = Column(Float, nullable=False)
    text_score = Column(Float, nullable=False)
    category_score = Column(Float, nullable=False)
    spatial_decay = Column(Float, nullable=False)
    temporal_decay = Column(Float, nullable=False)
    ocr_bonus = Column(Float, nullable=False)
    total_score = Column(Float, nullable=False, index=True)
    status = Column(Enum(MatchStatus), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Claim(Base):
    __tablename__ = "claims"
    
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    claimant_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    challenge_question = Column(String(500), nullable=False)
    claimant_answer = Column(String(500), nullable=False)
    is_challenge_approved = Column(Boolean, default=False)
    handshake_qr_token = Column(String(500))
    handover_by_user_id = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
