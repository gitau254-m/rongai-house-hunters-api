from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from app.core.database import get_db
from app.core.debs import require_role
from app.models.review import Review
from app.models.appointment import Appointment

router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"],
)


class ReviewCreate(BaseModel):
    property_id: UUID
    appointment_id: UUID  # links this review to a real verified viewing
    rating: int  # 1 to 5 stars
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_must_be_valid(cls, value):
        # The database also enforces this, but we catch it here first
        if value < 1 or value > 5:
            raise ValueError("Rating must be between 1 and 5 stars")
        return value


class ReviewResponse(BaseModel):
    id: UUID
    reviewer_id: UUID
    property_id: UUID
    appointment_id: Optional[UUID] = None
    rating: int
    comment: Optional[str] = None
    verified_viewing: bool  # True = customer physically visited
    is_hidden: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/", response_model=ReviewResponse, status_code=201)
async def create_review(
        data: ReviewCreate,
        current_user: dict = Depends(require_role(["customer"])),
        db: AsyncSession = Depends(get_db)
):
    """
    Customer leaves a review after a verified viewing.

    Rules:
    - The appointment must be COMPLETED (viewing code was verified)
    - The appointment must belong to this customer
    - One review per appointment — prevents duplicate reviews
    """

    # Step 1: find the appointment
    appt_result = await db.execute(
        select(Appointment).where(Appointment.id == data.appointment_id)
    )
    appointment = appt_result.scalar_one_or_none()

    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Step 2: appointment must belong to this customer
    if str(appointment.customer_id) != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only review your own viewings"
        )

    # Step 3: viewing must be completed (viewing code was entered and verified)
    if appointment.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="You can only review after a completed viewing"
        )

    # Step 4: prevent duplicate reviews for the same appointment
    existing_review = await db.execute(
        select(Review).where(Review.appointment_id == data.appointment_id)
    )
    if existing_review.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You have already reviewed this viewing"
        )

    # Step 5: create the review
    # verified_viewing = True because they completed the viewing code flow
    new_review = Review(
        id=uuid4(),
        reviewer_id=current_user["user_id"],
        property_id=data.property_id,
        appointment_id=data.appointment_id,
        rating=data.rating,
        comment=data.comment,
        verified_viewing=True,  # hardcoded True — only completed viewings reach here
        is_hidden=False,
    )

    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)
    return new_review


@router.get("/{property_id}", response_model=List[ReviewResponse])
async def get_property_reviews(
        property_id: UUID,
        db: AsyncSession = Depends(get_db)
        # No auth required — reviews are public information
):
    """
    Returns all visible reviews for a property.
    Powers the reviews section on /houses/{id} listing page.
    Hidden reviews (moderated by admin) are excluded.
    """
    result = await db.execute(
        select(Review)
        .where(
            Review.property_id == property_id,
            Review.is_hidden == False  # never show hidden reviews to public
        )
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()