from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.security import create_qr_token, verify_token, get_current_user_id, require_admin
from app.models.match import Match, Claim
from app.models.item import Item, ItemStatus
from app.models.user import User
from app.schemas.match import (
    ClaimCreate,
    ClaimResponse,
    QRHandshakeResponse,
    ChallengeRespondRequest,
    ChallengeApproveRequest,
    HandshakeVerifyRequest,
)

router = APIRouter()

@router.post("/challenge/create", response_model=ClaimResponse)
async def create_challenge(
    claim: ClaimCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Create a claim with verification challenge"""

    match = db.query(Match).filter(Match.id == claim.match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Create claim
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
    """Submit answer to verification challenge"""

    claim = db.query(Claim).filter(Claim.id == request.claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.claimant_id != user_id:
        raise HTTPException(status_code=403, detail="Not your claim")

    claim.claimant_answer = request.answer
    db.commit()
    db.refresh(claim)
    
    return ClaimResponse.from_orm(claim)

@router.post("/challenge/approve", response_model=QRHandshakeResponse)
async def approve_challenge(
    request: ChallengeApproveRequest,
    db: Session = Depends(get_db),
    approver_id: int = Depends(get_current_user_id)
):
    """Approve claim and issue QR handshake token"""

    claim_id = request.claim_id
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Only the person who reported the found item may approve the claim on it
    match = db.query(Match).filter(Match.id == claim.match_id).first()
    found_item = db.query(Item).filter(Item.id == match.found_item_id).first() if match else None
    if not found_item:
        raise HTTPException(status_code=404, detail="Matched item not found")
    if found_item.user_id != approver_id:
        raise HTTPException(status_code=403, detail="Only the finder can approve this claim")

    # Generate time-bound QR token (15 minutes)
    qr_token = create_qr_token(
        data={
            "claim_id": claim_id,
            "match_id": claim.match_id,
            "claimant_id": claim.claimant_id
        }
    )
    
    claim.is_challenge_approved = True
    claim.handshake_qr_token = qr_token
    
    db.commit()
    db.refresh(claim)
    
    # Get found item for response
    match = db.query(Match).filter(Match.id == claim.match_id).first()
    
    return QRHandshakeResponse(
        qr_token=qr_token,
        expires_in_minutes=15,
        item_id=match.found_item_id if match else 0
    )

@router.post("/handshake/verify")
async def verify_handshake(
    request: HandshakeVerifyRequest,
    admin_user_id: int = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Verify QR handshake token and complete handover"""

    # Verify token
    payload = verify_token(request.qr_token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired QR token")

    claim_id = payload.get("claim_id")
    claim = db.query(Claim).filter(Claim.id == claim_id).first()

    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not claim.is_challenge_approved:
        raise HTTPException(status_code=400, detail="Claim has not been approved")

    if claim.resolved_at:
        raise HTTPException(status_code=400, detail="This handover is already complete")

    # Update claim. The staff member comes from the token, not the request body.
    claim.handover_by_user_id = admin_user_id
    claim.resolved_at = datetime.utcnow()

    # Update match
    match = db.query(Match).filter(Match.id == claim.match_id).first()
    if match:
        # Update item statuses
        found_item = db.query(Item).filter(Item.id == match.found_item_id).first()
        lost_item = db.query(Item).filter(Item.id == match.lost_item_id).first()

        if found_item:
            found_item.status = ItemStatus.RESOLVED
        if lost_item:
            lost_item.status = ItemStatus.RESOLVED

        # Award karma to finder
        if found_item:
            finder = db.query(User).filter(User.id == found_item.user_id).first()
            if finder:
                finder.karma_score += 25

    db.commit()
    
    return {
        "status": "success",
        "message": "Item handover verified",
        "claim_id": claim_id,
        "resolved_at": claim.resolved_at
    }
