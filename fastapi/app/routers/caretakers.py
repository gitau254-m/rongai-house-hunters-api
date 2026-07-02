from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.models.profile import Profile
from app.models.caretaker import Caretaker
from app.models.property import Property

router = APIRouter(
    prefix="/caretakers",
    tags=["Caretakers"],
)


# ── Schema: what we return for a public caretaker profile ────────────
class CaretakerPublicResponse(BaseModel):
    id: UUID
    full_name: str               # from profiles table
    trust_tier: int              # 1=New, 2=Trusted, 3=Partner
    verification_status: str
    approved_listings_count: int
    business_name: Optional[str] = None
    member_since: Optional[datetime] = None   # profiles.created_at
    live_listing_count: int       # how many of their listings are currently live

    model_config = {"from_attributes": True}


@router.get("/{caretaker_id}", response_model=CaretakerPublicResponse)
async def get_caretaker_profile(
    caretaker_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the PUBLIC profile of a caretaker.
    Used on the listing detail page to show caretaker info.
    We deliberately hide: national ID, phone, documents, admin notes.
    We show: name, tier badge, how long they've been on the platform.
    """

    # Step 1: get the caretaker record
    caretaker_result = await db.execute(
        select(Caretaker).where(Caretaker.id == caretaker_id)
    )
    caretaker = caretaker_result.scalar_one_or_none()

    if caretaker is None:
        raise HTTPException(status_code=404, detail="Caretaker not found")

    if caretaker.verification_status != "verified":
        # Don't expose unverified caretakers publicly
        raise HTTPException(status_code=404, detail="Caretaker not found")

    # Step 2: get their profile (for name and join date)
    profile_result = await db.execute(
        select(Profile).where(Profile.id == caretaker_id)
    )
    profile = profile_result.scalar_one_or_none()

    if profile is None:
        raise HTTPException(status_code=404, detail="Caretaker not found")

    # Step 3: count their currently live listings
    live_count_result = await db.execute(
        select(Property).where(
            Property.caretaker_id == caretaker_id,
            Property.status == "live"
        )
    )
    live_listings = live_count_result.scalars().all()

    # Step 4: build and return the response
    # We manually assemble this because it combines data from 3 queries
    return CaretakerPublicResponse(
        id=caretaker.id,
        full_name=profile.full_name,
        trust_tier=caretaker.trust_tier,
        verification_status=caretaker.verification_status,
        approved_listings_count=caretaker.approved_listings_count,
        business_name=caretaker.business_name,
        member_since=profile.created_at,
        live_listing_count=len(live_listings),
    )