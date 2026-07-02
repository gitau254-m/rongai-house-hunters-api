from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True)
    customer_id = Column(UUID(as_uuid=True), nullable=False)    # FK → profiles
    property_id = Column(UUID(as_uuid=True), nullable=False)    # FK → properties
    caretaker_id = Column(UUID(as_uuid=True), nullable=False)   # FK → profiles
    preferred_date = Column(Date, nullable=False)
    preferred_time = Column(String, nullable=False)
    number_of_viewers = Column(Integer, default=1)
    notes = Column(String)

    # Status flow: requested → confirmed → completed (or cancelled/no_show)
    status = Column(String, default="requested")

    # The 4-digit anti-fraud code (Section 8 of your docs)
    viewing_code = Column(String)
    viewing_code_expires_at = Column(DateTime(timezone=True))

    # Both sides confirm when code is entered
    customer_confirmed_at = Column(DateTime(timezone=True))
    caretaker_confirmed_at = Column(DateTime(timezone=True))

    # Confirmed date/time (caretaker may choose from alt dates)
    confirmed_date = Column(Date)
    confirmed_time = Column(String)

    # Reschedule fields
    reschedule_date = Column(Date)
    reschedule_time = Column(String)
    reschedule_reason = Column(String)
    cancellation_reason = Column(String)

    # Dispute (24h window after completion)
    dispute_raised = Column(Boolean, default=False)
    dispute_raised_at = Column(DateTime(timezone=True))
    dispute_reason = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())