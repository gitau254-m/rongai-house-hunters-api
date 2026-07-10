from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import List
from uuid import UUID, uuid4
from datetime import datetime

from app.core.database import get_db
from app.core.debs import require_role
from app.models.favourite import Favourite
from app.models.property import Property

router = APIRouter(
    prefix="/favourites",
    tags=["Favourites"],
)


# ── Response schema ──────────────────────────────────────────────────
class FavouriteResponse(BaseModel):
    id: UUID
    customer_id: UUID
    property_id: UUID
    saved_at: datetime

    model_config = {"from_attributes": True}


@router.post("/", response_model=FavouriteResponse, status_code=201)
async def save_favourite(
    property_id: UUID,
    # Only customers can save favourites
    current_user: dict = Depends(require_role(["customer"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Customer saves a property to their favourites list.
    The heart icon on every listing card calls this endpoint.
    """

    # Step 1: make sure the property actually exists and is live
    property_result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    house = property_result.scalar_one_or_none()

    if house is None:
        raise HTTPException(status_code=404, detail="Property not found")

    # Step 2: check if already saved — prevent duplicates
    # The database has a UNIQUE constraint on (customer_id, property_id)
    # but we catch it here first for a friendlier error message
    existing = await db.execute(
        select(Favourite).where(
            Favourite.customer_id == current_user["user_id"],
            Favourite.property_id == property_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You have already saved this property"
        )

    # Step 3: save it
    new_favourite = Favourite(
        id=uuid4(),
        customer_id=current_user["user_id"],
        property_id=property_id,
    )

    db.add(new_favourite)

    # Step 4: increment the property's saves_count
    # This is how a caretaker knows their listing is popular
    house.saves_count = (house.saves_count or 0) + 1

    await db.commit()
    await db.refresh(new_favourite)
    return new_favourite


@router.delete("/{property_id}", status_code=200)
async def remove_favourite(
    property_id: UUID,
    current_user: dict = Depends(require_role(["customer"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Removes a property from the customer's favourites.
    The heart icon (when already filled) calls this to un-save.
    """

    # Find the favourite record first
    result = await db.execute(
        select(Favourite).where(
            Favourite.customer_id == current_user["user_id"],
            Favourite.property_id == property_id
        )
    )
    favourite = result.scalar_one_or_none()

    if favourite is None:
        raise HTTPException(
            status_code=404,
            detail="This property is not in your favourites"
        )

    # Decrement the property's saves_count
    property_result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    house = property_result.scalar_one_or_none()
    if house and house.saves_count and house.saves_count > 0:
        house.saves_count -= 1

    # Delete the favourite record
    await db.execute(
        delete(Favourite).where(
            Favourite.customer_id == current_user["user_id"],
            Favourite.property_id == property_id
        )
    )

    await db.commit()
    return {"message": "Removed from favourites"}


@router.get("/my", response_model=List[FavouriteResponse])
async def get_my_favourites(
    current_user: dict = Depends(require_role(["customer"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all properties saved by this customer.
    Powers the /dashboard/customer/favourites page.
    """
    result = await db.execute(
        select(Favourite)
        .where(Favourite.customer_id == current_user["user_id"])
        .order_by(Favourite.saved_at.desc())  # most recently saved first
    )
    return result.scalars().all()