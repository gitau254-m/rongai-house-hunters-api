from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role = Column(String, default="customer")
    full_name = Column(String, nullable=False)
    phone_number = Column(String)
    email = Column(String)
    status = Column(String, default="active")
    avatar_url = Column(String)
    password_hash = Column(String)    # ← we added this to the DB in Step 1
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())