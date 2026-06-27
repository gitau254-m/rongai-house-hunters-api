from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ── What the API RETURNS when you fetch a property ──────────────────
class PropertyResponse(BaseModel):
    id: UUID
    title: str
    property_type: str
    rent_amount: int
    deposit_amount: int
    service_charge: int
    availability_status: str
    level1_area: str
    level2_estate: str
    landmark_proximity: Optional[List[str]] = []
    amenities: Optional[List[str]] = []
    status: str
    views_count: int
    saves_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── What the API ACCEPTS when a caretaker creates a listing ─────────
class PropertyCreate(BaseModel):
    title: str
    property_type: str        # single | bedsitter | 1_bedroom | 2_bedroom
    rent_amount: int
    deposit_amount: int
    service_charge: int = 0   # optional — defaults to 0 if not sent
    availability_status: str = "vacant_now"
    level1_area: str
    level2_estate: str
    landmark_proximity: Optional[List[str]] = []
    location_privacy_mode: str = "approximate"
    description: str
    amenities: Optional[List[str]] = []
    house_rules: Optional[str] = None
    contact_preference: List[str]
         # later this will come from the login token

    # ── Validation — Pydantic checks these BEFORE touching the database ──
    @field_validator("rent_amount")
    @classmethod
    def rent_must_be_reasonable(cls, value):
        if value < 2000:
            raise ValueError("Rent must be at least Ksh 2,000")
        if value > 200000:
            raise ValueError("Rent seems too high — check the amount")
        return value

    @field_validator("property_type")
    @classmethod
    def valid_property_type(cls, value):
        allowed = ["single", "bedsitter", "1_bedroom", "2_bedroom"]
        value = value.lower()
        if value not in allowed:
            raise ValueError(f"property_type must be one of: {allowed}")
        return value

    @field_validator("description")
    @classmethod
    def description_long_enough(cls, value):
        if len(value) < 20:
            raise ValueError("Description must be at least 20 characters")
        return value