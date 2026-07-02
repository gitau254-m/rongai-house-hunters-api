from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Caretaker(Base):
    __tablename__ = "caretakers"

    # This ID is a FOREIGN KEY to profiles.id
    # A caretaker IS a profile — same UUID, two tables
    # This is called a "one-to-one" relationship
    id = Column(UUID(as_uuid=True), primary_key=True)
    national_id_number = Column(String, unique=True)
    date_of_birth = Column(Date)
    county = Column(String)
    current_address = Column(String)
    role_claim = Column(String)   # owner | caretaker | agent | property_manager
    business_name = Column(String)
    whatsapp_number = Column(String)
    id_front_url = Column(String)
    selfie_url = Column(String)
    selfie_holding_id_url = Column(String)
    proof_document_url = Column(String)
    verification_status = Column(String, default="pending")
    trust_tier = Column(Integer, default=1)   # 1 = New, 2 = Trusted, 3 = Partner
    approved_listings_count = Column(Integer, default=0)
    fraud_reports_count = Column(Integer, default=0)
    first_listing_used = Column(Boolean, default=False)
    accepted_terms = Column(Boolean, default=False)
    referral_code = Column(String, unique=True)
    verified_at = Column(DateTime(timezone=True))
    rejection_reason = Column(String)
    admin_notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())