from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.core.debs import require_role
from app.models.property import Property
from app.schemas.property import PropertyResponse, PropertyCreate  # ← add PropertyCreate

router = APIRouter(
    prefix="/houses",
    tags=["Houses"],
)


@router.get("/", response_model=List[PropertyResponse])
async def get_all_houses(
    area: Optional[str] = None,
    min_rent: Optional[int] = None,
    max_rent: Optional[int] = None,
    property_type: Optional[str] = None,
    availability: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Property).where(Property.status == "live")
    if area:
        query = query.where(Property.level1_area == area)
    if min_rent:
        query = query.where(Property.rent_amount >= min_rent)
    if max_rent:
        query = query.where(Property.rent_amount <= max_rent)
    if property_type:
        query = query.where(Property.property_type == property_type)
    if availability:
        query = query.where(Property.availability_status == availability)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/my/listings", response_model=List[PropertyResponse])
async def get_my_listings(
    # Optional filter by status — for the tabs: All | Live | Pending | Rejected
    status: Optional[str] = None,
    current_user: dict = Depends(require_role(["caretaker"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Caretaker sees their own listings.
    Powers the dashboard cards:
    Total Listings | Live Now | Pending | Views (7d)
    """
    # Base query — only this caretaker's listings
    query = select(Property).where(
        Property.caretaker_id == current_user["user_id"]
    )

    # Optional status filter (frontend uses this for tabs)
    if status:
        query = query.where(Property.status == status)

    # Most recent first
    query = query.order_by(Property.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{house_id}", response_model=PropertyResponse)
async def get_single_house(house_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Property).where(Property.id == house_id)
    )
    house = result.scalar_one_or_none()
    if house is None:
        raise HTTPException(status_code=404, detail=f"House {house_id} not found")
    return house


# ── NEW ENDPOINT ─────────────────────────────────────────────────────
@router.post("/", response_model=PropertyResponse, status_code=201)
async def create_house(
    house_data: PropertyCreate,    # ← FastAPI reads the JSON body into this object
    current_user: dict = Depends(require_role(["caretaker"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new property listing.
    Status starts as 'pending_review' — admin must approve before it goes live.
    This matches RHH business logic: no listing appears without admin approval.
    """

    # Convert the Pydantic schema into a SQLAlchemy model object
    new_house = Property(
        caretaker_id=current_user["user_id"],
        title=house_data.title,
        property_type=house_data.property_type,
        rent_amount=house_data.rent_amount,
        deposit_amount=house_data.deposit_amount,
        service_charge=house_data.service_charge,
        availability_status=house_data.availability_status,
        level1_area=house_data.level1_area,
        level2_estate=house_data.level2_estate,
        landmark_proximity=house_data.landmark_proximity,
        location_privacy_mode=house_data.location_privacy_mode,
        description=house_data.description,
        amenities=house_data.amenities,
        house_rules=house_data.house_rules,
        contact_preference=house_data.contact_preference,
        status="pending_review",   # ← hardcoded — caretakers cannot set this themselves
    )

    db.add(new_house)          # stage the new row
    await db.commit()          # write it to PostgreSQL
    await db.refresh(new_house)  # reload from DB to get the generated ID and timestamps
    return new_house