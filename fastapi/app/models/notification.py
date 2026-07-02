from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)   # FK → profiles
    type = Column(String, nullable=False)     # e.g. "appointment_confirmed"
    title = Column(String, nullable=False)    # e.g. "Your viewing is confirmed!"
    message = Column(String, nullable=False)  # full text
    link = Column(String)                     # where to navigate on click
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())