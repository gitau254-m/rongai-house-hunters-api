import random
import string
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID, uuid4
from datetime import date, datetime, timezone, timedelta

from app.core.database import get_db
from app.core.debs import require_role, get_current_user
from app.models.appointment import Appointment
from app.models.property import Property

router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)


# ── Schema: what a customer sends to book a viewing ──────────────────
class AppointmentCreate(BaseModel):
    property_id: UUID
    preferred_date: date           # format: "2026-07-15"
    preferred_time: str            # format: "10:00 AM"
    number_of_viewers: int = 1
    notes: Optional[str] = None   # any extra message to caretaker

    @field_validator("preferred_date")
    @classmethod
    def date_must_be_future(cls, value):
        # Prevents booking appointments in the past
        if value < date.today():
            raise ValueError("Appointment date must be today or in the future")
        return value

    @field_validator("number_of_viewers")
    @classmethod
    def viewers_reasonable(cls, value):
        if value < 1 or value > 10:
            raise ValueError("Number of viewers must be between 1 and 10")
        return value


# ── Schema: what we return after booking ─────────────────────────────
class AppointmentResponse(BaseModel):
    id: UUID
    customer_id: UUID
    property_id: UUID
    caretaker_id: UUID
    preferred_date: date
    preferred_time: str
    number_of_viewers: int
    notes: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/", response_model=AppointmentResponse, status_code=201)
async def book_appointment(
    data: AppointmentCreate,
    # Only logged-in customers can book — caretakers cannot book their own listings
    current_user: dict = Depends(require_role(["customer"])),
    db: AsyncSession = Depends(get_db)
):
    """
    A customer books a viewing for a property.
    The caretaker_id is pulled from the property — customer never sends it.
    Status starts as 'requested' — caretaker must confirm.
    """

    # Step 1: verify the property exists and is available
    property_result = await db.execute(
        select(Property).where(Property.id == data.property_id)
    )
    house = property_result.scalar_one_or_none()

    if house is None:
        raise HTTPException(status_code=404, detail="Property not found")

    if house.status != "live":
        raise HTTPException(
            status_code=400,
            detail="This property is not available for viewing"
        )

    if house.availability_status == "occupied":
        raise HTTPException(
            status_code=400,
            detail="This property is occupied. Join the waitlist instead."
        )

    # Step 2: create the appointment
    # caretaker_id comes from the property record — not from the customer
    new_appointment = Appointment(
        id=uuid4(),
        customer_id=current_user["user_id"],   # from JWT token
        property_id=data.property_id,
        caretaker_id=house.caretaker_id,       # from the property — reliable
        preferred_date=data.preferred_date,
        preferred_time=data.preferred_time,
        number_of_viewers=data.number_of_viewers,
        notes=data.notes,
        status="requested",                    # caretaker must confirm this
    )

    db.add(new_appointment)

    # Step 3: increment the property's appointment counter
    # This is how caretakers know how popular their listing is
    house.appointment_requests_count = (house.appointment_requests_count or 0) + 1

    await db.commit()
    await db.refresh(new_appointment)
    return new_appointment


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    # Both customers and caretakers can view appointments — not the general public
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a single appointment.
    A customer can only see their own appointment.
    A caretaker can only see appointments on their properties.
    An admin can see all.
    """
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Access control — you can only see appointments you are part of
    user_id = current_user["user_id"]
    role = current_user["role"]

    if role not in ["admin", "super_admin"]:
        is_customer = str(appointment.customer_id) == user_id
        is_caretaker = str(appointment.caretaker_id) == user_id
        if not is_customer and not is_caretaker:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this appointment"
            )

    return appointment


@router.put("/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: UUID,
    current_user: dict = Depends(require_role(["caretaker"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Caretaker confirms a requested appointment.
    Only the caretaker who owns the property can confirm.
    """
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Make sure this caretaker owns this appointment
    if str(appointment.caretaker_id) != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only confirm appointments for your own properties"
        )

    if appointment.status != "requested":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm an appointment with status '{appointment.status}'"
        )

    appointment.status = "confirmed"
    appointment.caretaker_confirmed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"message": "Appointment confirmed", "appointment_id": str(appointment_id)}


@router.post("/{appointment_id}/code")
async def generate_viewing_code(
    appointment_id: UUID,
    current_user: dict = Depends(require_role(["caretaker"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Caretaker generates a 4-digit viewing code on the day of the appointment.
    This is the anti-fraud mechanism from Section 8 of your RHH docs.
    The customer enters this code to confirm they physically attended.
    """
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if str(appointment.caretaker_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your appointment")

    if appointment.status != "confirmed":
        raise HTTPException(
            status_code=400,
            detail="Appointment must be confirmed before generating a code"
        )

    # Generate 4 random digits — simple but effective for in-person verification
    # random.choices picks from a list, k=4 means pick 4 items
    code = "".join(random.choices(string.digits, k=4))

    appointment.viewing_code = code
    # Code expires after 24 hours (prevents reuse the next day)
    appointment.viewing_code_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    await db.commit()

    return {
        "viewing_code": code,
        "expires_at": appointment.viewing_code_expires_at,
        "message": "Show this code to your customer"
    }


@router.post("/{appointment_id}/verify")
async def verify_viewing_code(
    appointment_id: UUID,
    code: str,                # the 4-digit code the customer types
    current_user: dict = Depends(require_role(["customer"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Customer enters the 4-digit code from the caretaker.
    If valid: appointment → 'completed', both sides confirmed.
    This is what triggers commission payment later (in DEV_MODE=false).
    """
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Only the customer of this appointment can verify
    if str(appointment.customer_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your appointment")

    # Prevent re-verification (single-use code)
    if appointment.customer_confirmed_at is not None:
        raise HTTPException(status_code=400, detail="This viewing has already been confirmed")

    # Check if code exists
    if appointment.viewing_code is None:
        raise HTTPException(
            status_code=400,
            detail="No viewing code generated yet. Ask your caretaker."
        )

    # Check if code expired
    if datetime.now(timezone.utc) > appointment.viewing_code_expires_at:
        raise HTTPException(
            status_code=400,
            detail="Code expired. Ask caretaker to generate a new one."
        )

    # Check if code matches
    if code != appointment.viewing_code:
        raise HTTPException(status_code=400, detail="Incorrect code. Check with your caretaker.")

    # All checks passed — mark as completed
    now = datetime.now(timezone.utc)
    appointment.customer_confirmed_at = now
    appointment.caretaker_confirmed_at = now
    appointment.status = "completed"

    await db.commit()

    return {
        "message": "Viewing confirmed! You can now leave a review.",
        "appointment_id": str(appointment_id),
        "status": "completed"
    }