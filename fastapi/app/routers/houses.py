from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
import hashlib
import json

from app.core.database import get_db
from app.core.debs import require_role
from app.core.cache import get_redis_client, get_cached, set_cached, invalidate_cache, HOUSES_ALL_KEY, HOUSES_FILTER_KEY, CACHE_TTL
from app.models.property import Property
from app.schemas.property import PropertyResponse, PropertyCreate
import redis.asyncio as aioredis

router = APIRouter(prefix="/houses", tags=["Houses"])


@router.get("/", response_model=List[PropertyResponse])
async def get_all_houses(
        area: Optional[str] = None,
        min_rent: Optional[int] = None,
        max_rent: Optional[int] = None,
        property_type: Optional[str] = None,
        availability: Optional[str] = None,
        page: int = 1,  # ← which page (default: first page)
        limit: int = 20,  # ← how many per page (default: 20)
        db: AsyncSession = Depends(get_db),
        cache: aioredis.Redis = Depends(get_redis_client)
):
    """
    Returns live properties with optional filters and pagination.

    Examples:
    /houses/?page=1&limit=20    → first 20 houses
    /houses/?page=2&limit=20    → next 20 houses
    /houses/?page=1&limit=5     → first 5 houses (for mobile quick load)
    """

    # Validate pagination inputs
    # Prevent someone sending page=0 or limit=10000
    if page < 1:
        page = 1
    if limit < 1 or limit > 100:  # max 100 per page — protects your DB
        limit = 20

    # Calculate how many rows to skip
    # Page 1: skip 0   (rows 1-20)
    # Page 2: skip 20  (rows 21-40)
    # Page 3: skip 40  (rows 41-60)
    offset = (page - 1) * limit

    # Build unique cache key that includes pagination
    filter_params = {
        "area": area,
        "min_rent": min_rent,
        "max_rent": max_rent,
        "property_type": property_type,
        "availability": availability,
        "page": page,
        "limit": limit,
    }
    active_filters = {k: v for k, v in filter_params.items() if v is not None}
    filter_string = json.dumps(active_filters, sort_keys=True)
    filter_hash = hashlib.md5(filter_string.encode()).hexdigest()[:8]
    cache_key = f"rhh:houses:p{page}:{filter_hash}"

    cached_result = await get_cached(cache, cache_key)
    if cached_result is not None:
        return cached_result

    # Build query with filters
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

    # Apply pagination — OFFSET skips rows, LIMIT caps results
    query = query.order_by(Property.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    properties = result.scalars().all()

    properties_data = [
        PropertyResponse.model_validate(p).model_dump(mode="json")
        for p in properties
    ]

    await set_cached(cache, cache_key, properties_data)
    return properties_data

@router.get("/my/listings", response_model=List[PropertyResponse])
async def get_my_listings(
    status: Optional[str] = None,
    current_user: dict = Depends(require_role(["caretaker"])),
    db: AsyncSession = Depends(get_db)
):
    """Caretaker sees their own listings. Not cached — caretakers need live data."""
    query = select(Property).where(
        Property.caretaker_id == current_user["user_id"]
    )
    if status:
        query = query.where(Property.status == status)
    query = query.order_by(Property.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{house_id}", response_model=PropertyResponse)
async def get_single_house(
    house_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Returns one property by ID. Not cached — views_count changes frequently."""
    result = await db.execute(select(Property).where(Property.id == house_id))
    house = result.scalar_one_or_none()
    if house is None:
        raise HTTPException(status_code=404, detail=f"House {house_id} not found")

    # Increment view count every time the listing detail page is opened
    house.views_count = (house.views_count or 0) + 1
    await db.commit()
    await db.refresh(house)
    return house


@router.post("/", response_model=PropertyResponse, status_code=201)
async def create_house(
    house_data: PropertyCreate,
    current_user: dict = Depends(require_role(["caretaker"])),
    db: AsyncSession = Depends(get_db),
    cache: aioredis.Redis = Depends(get_redis_client)
):
    """
    Creates a new listing.
    After creation, we invalidate the houses cache so the
    new listing appears in search results on the next request.
    """
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
        status="pending_review",
    )

    db.add(new_house)
    await db.commit()
    await db.refresh(new_house)

    # Invalidate ALL houses cache entries
    # Because a new listing was created, cached search results are now stale
    await invalidate_cache(cache, "rhh:houses:*")

    return new_house