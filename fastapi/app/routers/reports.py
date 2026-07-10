from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from uuid import UUID, uuid4

from app.core.database import get_db
from app.core.debs import get_current_user
from app.models.report import Report

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)

# All valid report types — matches your database CHECK constraint exactly
VALID_REPORT_TYPES = [
    "fake_listing",
    "wrong_location",
    "duplicate",
    "scam_attempt",
    "unavailable_house",
    "abusive_caretaker",
    "false_information",
    "other"
]


class ReportCreate(BaseModel):
    property_id: Optional[UUID] = None  # can report a listing
    caretaker_id: Optional[UUID] = None  # or a caretaker directly
    report_type: str
    details: Optional[str] = None  # free text description


@router.post("/", status_code=201)
async def submit_report(
        data: ReportCreate,
        # Any logged-in user can submit a report — customers, caretakers, even admins
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Any logged-in user can report a suspicious listing or caretaker.
    Powers the floating 🚩 Report button on every listing detail page.

    The admin dashboard fraud queue reads from this table.
    Your database trigger watches this table:
    when 3+ distinct users report the same property → auto-flag it.
    """

    # Validate report type against allowed list
    if data.report_type not in VALID_REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report type. Must be one of: {VALID_REPORT_TYPES}"
        )

    # Must report SOMETHING — either a property or a caretaker (or both)
    if data.property_id is None and data.caretaker_id is None:
        raise HTTPException(
            status_code=400,
            detail="You must provide either a property_id or caretaker_id to report"
        )

    new_report = Report(
        id=uuid4(),
        reporter_id=current_user["user_id"],
        property_id=data.property_id,
        caretaker_id=data.caretaker_id,
        report_type=data.report_type,
        details=data.details,
        status="open",  # admin picks it up from here
    )

    db.add(new_report)
    await db.commit()

    return {
        "message": "Report submitted. Our team will review it within 24 hours.",
        "report_type": data.report_type
    }