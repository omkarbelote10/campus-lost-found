from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class MatchResponse(BaseModel):
    id: int
    lost_item_id: int
    found_item_id: int
    visual_score: float
    text_score: float
    category_score: float
    spatial_decay: float
    temporal_decay: float
    ocr_bonus: float
    total_score: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class MatchedItemSummary(BaseModel):
    """Enough of the counterpart item to render a match card without a second request."""
    id: int
    title: str
    type: str
    category: str
    campus_zone: str
    image_urls: List[str] = []
    is_high_value: bool = False
    incident_time: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class EnrichedMatchResponse(MatchResponse):
    """A match plus both sides of it, from the perspective of the requesting user."""
    your_item: MatchedItemSummary
    matched_item: MatchedItemSummary

class FindMatchesRequest(BaseModel):
    item_id: int

class ClaimCreate(BaseModel):
    match_id: int
    challenge_question: str
    claimant_answer: str

class ChallengeRespondRequest(BaseModel):
    claim_id: int
    answer: str

class ChallengeApproveRequest(BaseModel):
    claim_id: int

class ClaimResponse(BaseModel):
    id: int
    match_id: int
    claimant_id: int
    challenge_question: str
    is_challenge_approved: bool
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True
