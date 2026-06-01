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
async def get_all_houses(db: AsyncSession = Depends(get_db)):
    """Returns all live properties."""
    result = await db.execute(
        select(Property).where(Property.status == "live")
    )
    return result.scalars().all()


# ← ADD THIS NEW ENDPOINT BELOW
@router.get("/{house_id}", response_model=PropertyResponse)
async def get_single_house(house_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Returns one property by its ID.
    UUID means the ID must be a valid UUID format like:
    550e8400-e29b-41d4-a716-446655440000
    """
    result = await db.execute(
        select(Property).where(Property.id == house_id)
    )
    house = result.scalar_one_or_none()

    # If no house found with that ID, return a 404 error
    if house is None:
        raise HTTPException(
            status_code=404,
            detail=f"House with ID {house_id} not found"
        )

    return house