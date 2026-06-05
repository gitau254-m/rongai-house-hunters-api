from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.models.property import Property
from app.schemas.property import PropertyResponse

router = APIRouter(
    prefix="/houses",
    tags=["Houses"],
)


@router.get("/", response_model=List[PropertyResponse])
async def get_all_houses(
        # Each of these becomes a query parameter automatically.
        # They are all optional — if not provided, they default to None.
        area: Optional[str] = None,
        min_rent: Optional[int] = None,
        max_rent: Optional[int] = None,
        property_type: Optional[str] = None,
        availability: Optional[str] = None,
        db: AsyncSession = Depends(get_db)
):
    """
    Returns live properties with optional filters.

    Examples:
    /houses/?area=Ongata Rongai
    /houses/?min_rent=3000&max_rent=8000
    /houses/?property_type=bedsitter
    /houses/?area=Rimpa&max_rent=6000&property_type=single
    """

    # Start with the base query — only live properties
    query = select(Property).where(Property.status == "live")

    # Add filters one by one — only if the caller provided them
    # This is called "building a query dynamically"
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

    # Execute the final built query
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{house_id}", response_model=PropertyResponse)
async def get_single_house(
        house_id: UUID,
        db: AsyncSession = Depends(get_db)
):
    """Returns one property by its ID."""
    result = await db.execute(
        select(Property).where(Property.id == house_id)
    )
    house = result.scalar_one_or_none()

    if house is None:
        raise HTTPException(
            status_code=404,
            detail=f"House with ID {house_id} not found"
        )

    return house