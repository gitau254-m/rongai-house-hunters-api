from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True)
    reporter_id = Column(UUID(as_uuid=True), nullable=False)
    property_id = Column(UUID(as_uuid=True))     # nullable — can report a caretaker
    caretaker_id = Column(UUID(as_uuid=True))    # nullable — can report just a listing
    report_type = Column(String, nullable=False)
    details = Column(Text)
    status = Column(String, default="open")
    admin_notes = Column(Text)
    resolved_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())