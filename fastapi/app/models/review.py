from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True)
    reviewer_id = Column(UUID(as_uuid=True), nullable=False)
    property_id = Column(UUID(as_uuid=True), nullable=False)
    appointment_id = Column(UUID(as_uuid=True))     # links to the verified viewing
    rating = Column(Integer, nullable=False)         # 1–5 only (DB enforces this)
    comment = Column(Text)
    verified_viewing = Column(Boolean, default=False) # True = real tenant, shows badge
    is_hidden = Column(Boolean, default=False)        # admin can hide abusive reviews
    created_at = Column(DateTime(timezone=True), server_default=func.now())