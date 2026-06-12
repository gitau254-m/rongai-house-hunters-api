from sqlalchemy import Column, String, Integer, Float, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class Property(Base):
    # This tells SQLAlchemy which table in your database this maps to.
    # Must match exactly: "properties" (lowercase, plural).
    __tablename__ = "properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caretaker_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String, nullable=False)
    property_type = Column(String, nullable=False)
    rent_amount = Column(Integer, nullable=False)
    deposit_amount = Column(Integer, nullable=False)
    service_charge = Column(Integer, default=0)
    availability_status = Column(String, default="vacant_now")
    level1_area = Column(String, nullable=False)
    level2_estate = Column(String, nullable=False)
    landmark_proximity = Column(ARRAY(String))
    latitude = Column(Float)
    longitude = Column(Float)
    location_privacy_mode = Column(String, default="approximate")
    description = Column(Text, nullable=False)
    amenities = Column(ARRAY(String))
    house_rules = Column(Text)
    contact_preference = Column(ARRAY(String), nullable=False)
    status = Column(String, default="draft")
    views_count = Column(Integer, default=0)
    saves_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())