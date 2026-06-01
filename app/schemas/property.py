from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# There is a very important difference between a Model and a Schema.
# Model = the database table definition (in app/models/)
# Schema = what the API accepts and returns (in app/schemas/)
#
# Why separate? The database might store a password hash.
# The schema decides: I will NEVER return the password hash to the API caller.
# You control what goes in and what comes out.

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
    # from_attributes=True means:
    # "Take a SQLAlchemy Property object and convert it to this schema automatically"