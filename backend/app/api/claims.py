from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.match import Match, Claim
from app.models.item import Item, ItemStatus
from app.models.user import User
from app.schemas.match import (
    ClaimCreate,
    ClaimResponse,
    ChallengeRespondRequest,
    ChallengeApproveRequest,
)

router = APIRouter()

KARMA_REWARD_FOR_FINDER = 25


@router.post("/challenge/create", response_model=ClaimResponse)
async def create_challenge(
    claim: ClaimCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Open a claim on a match, with an ownership question only the owner can answer."""

    match = db.query(Match).filter(Match.id == claim.match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    db_claim = Claim(
        match_id=claim.match_id,
        claimant_id=user_id,
        challenge_question=claim.challenge_question,
        claimant_answer=claim.claimant_answer,
        is_challenge_approved=False
    )

    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)

    return ClaimResponse.from_orm(db_claim)


@router.post("/challenge/respond", response_model=ClaimResponse)
async def respond_to_challenge(
    request: ChallengeRespondRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Submit or revise the answer to a verification challenge"""

    claim = db.query(Claim).filter(Claim.id == request.claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.claimant_id != user_id:
        raise HTTPException(status_code=403, detail="Not your claim")
    if claim.resolved_at:
        raise HTTPException(status_code=400, detail="This claim is already resolved")

    claim.claimant_answer = request.answer
    db.commit()
    db.refresh(claim)

    return ClaimResponse.from_orm(claim)


@router.post("/challenge/approve", response_model=ClaimResponse)
async def approve_challenge(
    request: ChallengeApproveRequest,
    db: Session = Depends(get_db),
    approver_id: int = Depends(get_current_user_id)
):
    """Approve a claim and complete the handover.

    Approval by the finder is the final step: both items move to RESOLVED and the
    finder is awarded karma. There is no separate QR handshake.
    """

    claim = db.query(Claim).filter(Claim.id == request.claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    match = db.query(Match).filter(Match.id == claim.match_id).first()
    found_item = db.query(Item).filter(Item.id == match.found_item_id).first() if match else None
    if not found_item:
        raise HTTPException(status_code=404, detail="Matched item not found")

    # Only the person who reported the found item may hand it over.
    if found_item.user_id != approver_id:
        raise HTTPException(status_code=403, detail="Only the finder can approve this claim")

    if claim.resolved_at:
        raise HTTPException(status_code=400, detail="This handover is already complete")

    claim.is_challenge_approved = True
    claim.resolved_at = datetime.utcnow()

    lost_item = db.query(Item).filter(Item.id == match.lost_item_id).first()
    found_item.status = ItemStatus.RESOLVED
    if lost_item:
        lost_item.status = ItemStatus.RESOLVED

    finder = db.query(User).filter(User.id == found_item.user_id).first()
    if finder:
        finder.karma_score += KARMA_REWARD_FOR_FINDER

    db.commit()
    db.refresh(claim)

    return ClaimResponse.from_orm(claim)
