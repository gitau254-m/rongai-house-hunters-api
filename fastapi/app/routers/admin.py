from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date

from app.core.database import get_db
from app.core.debs import require_role
from app.models.profile import Profile
from app.models.caretaker import Caretaker
from app.models.property import Property
from app.models.appointment import Appointment
from app.models.report import Report
from app.models.review import Review

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)

# Every endpoint in this router requires admin or super_admin role
# We apply this as a dependency at the router level
AdminOnly = Depends(require_role(["admin", "super_admin"]))


# ════════════════════════════════════════════════════════════════
# DASHBOARD STATS — The 6 live counter cards in your screenshot
# ════════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_dashboard_stats(
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all 6 counters for the admin dashboard.
    Your frontend polls this to keep cards updated.
    Later we'll replace polling with Supabase Realtime or WebSockets.
    """

    # Count caretakers pending KYC review
    pending_kyc = await db.execute(
        select(func.count()).select_from(Caretaker)
        .where(Caretaker.verification_status == "pending")
    )

    # Count listings waiting for admin approval
    pending_listings = await db.execute(
        select(func.count()).select_from(Property)
        .where(Property.status == "pending_review")
    )

    # Count currently live listings
    live_listings = await db.execute(
        select(func.count()).select_from(Property)
        .where(Property.status == "live")
    )

    # Count flagged listings (reported multiple times)
    flagged_listings = await db.execute(
        select(func.count()).select_from(Property)
        .where(Property.status == "flagged")
    )

    # Count open fraud reports
    open_reports = await db.execute(
        select(func.count()).select_from(Report)
        .where(Report.status == "open")
    )

    # Count viewings scheduled for today
    viewings_today = await db.execute(
        select(func.count()).select_from(Appointment)
        .where(
            Appointment.preferred_date == date.today(),
            Appointment.status == "confirmed"
        )
    )

    return {
        "pending_kyc": pending_kyc.scalar(),
        "pending_listings": pending_listings.scalar(),
        "live_listings": live_listings.scalar(),
        "flagged_listings": flagged_listings.scalar(),
        "open_reports": open_reports.scalar(),
        "viewings_today": viewings_today.scalar(),
    }


# ════════════════════════════════════════════════════════════════
# CARETAKER KYC — Review, approve, reject caretaker applications
# ════════════════════════════════════════════════════════════════

@router.get("/caretakers")
async def list_caretakers(
    verification_status: Optional[str] = None,  # pending | verified | rejected
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all caretakers. Used for the KYC queue.
    Filter by verification_status to see pending, verified, or rejected.
    """
    query = select(Caretaker)
    if verification_status:
        query = query.where(Caretaker.verification_status == verification_status)
    query = query.order_by(Caretaker.created_at.asc())  # oldest first (FIFO queue)

    result = await db.execute(query)
    caretakers = result.scalars().all()
    return caretakers


@router.get("/caretakers/{caretaker_id}")
async def get_caretaker_for_review(
    caretaker_id: UUID,
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """
    Full caretaker detail for the KYC review page.
    Includes documents, admin notes, ID number — everything.
    This is the admin-only view (more detail than public /caretakers/{id}).
    """
    caretaker_result = await db.execute(
        select(Caretaker).where(Caretaker.id == caretaker_id)
    )
    caretaker = caretaker_result.scalar_one_or_none()

    if caretaker is None:
        raise HTTPException(status_code=404, detail="Caretaker not found")

    profile_result = await db.execute(
        select(Profile).where(Profile.id == caretaker_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Return a combined view of profile + caretaker details
    return {
        "id": caretaker.id,
        "full_name": profile.full_name,
        "email": profile.email,
        "phone_number": profile.phone_number,
        "status": profile.status,
        "national_id_number": caretaker.national_id_number,
        "date_of_birth": caretaker.date_of_birth,
        "county": caretaker.county,
        "current_address": caretaker.current_address,
        "role_claim": caretaker.role_claim,
        "business_name": caretaker.business_name,
        "id_front_url": caretaker.id_front_url,
        "selfie_url": caretaker.selfie_url,
        "selfie_holding_id_url": caretaker.selfie_holding_id_url,
        "proof_document_url": caretaker.proof_document_url,
        "verification_status": caretaker.verification_status,
        "trust_tier": caretaker.trust_tier,
        "admin_notes": caretaker.admin_notes,
        "submitted_at": caretaker.created_at,
    }


class KYCDecision(BaseModel):
    decision: str         # "verified" | "rejected" | "needs_more_info"
    admin_notes: str      # REQUIRED — must explain reason (your own RHH rule)
    rejection_reason: Optional[str] = None


@router.put("/caretakers/{caretaker_id}/decision")
async def make_kyc_decision(
    caretaker_id: UUID,
    decision_data: KYCDecision,
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """
    Admin approves or rejects a caretaker KYC application.
    Notes are mandatory — from your RHH docs: actions without explanation
    are not allowed on the admin panel.
    """
    allowed_decisions = ["verified", "rejected", "needs_more_info", "suspended"]
    if decision_data.decision not in allowed_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Decision must be one of: {allowed_decisions}"
        )

    # Notes are REQUIRED for all decisions — admin accountability rule
    if not decision_data.admin_notes.strip():
        raise HTTPException(
            status_code=400,
            detail="Admin notes are required before making a KYC decision"
        )

    caretaker_result = await db.execute(
        select(Caretaker).where(Caretaker.id == caretaker_id)
    )
    caretaker = caretaker_result.scalar_one_or_none()

    if caretaker is None:
        raise HTTPException(status_code=404, detail="Caretaker not found")

    caretaker.verification_status = decision_data.decision
    caretaker.admin_notes = decision_data.admin_notes

    if decision_data.decision == "rejected":
        caretaker.rejection_reason = decision_data.rejection_reason

    if decision_data.decision == "verified":
        caretaker.verified_at = datetime.utcnow()
        caretaker.verified_by = current_user["user_id"]

    await db.commit()

    return {
        "message": f"Caretaker {decision_data.decision}",
        "caretaker_id": str(caretaker_id),
        "decided_by": current_user["user_id"]
    }


# ════════════════════════════════════════════════════════════════
# LISTING MODERATION — The 3-lane Kanban from your RHH docs
# ════════════════════════════════════════════════════════════════

@router.get("/listings")
async def list_properties_for_moderation(
    status: Optional[str] = None,   # pending_review | live | flagged
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns listings for admin moderation.
    No status filter = all listings.
    status=pending_review = Column 1 (manual review required)
    status=flagged = Column 3 (reported listings, sort by report count)
    """
    query = select(Property)
    if status:
        query = query.where(Property.status == status)
    query = query.order_by(Property.created_at.asc())

    result = await db.execute(query)
    return result.scalars().all()


class ListingDecision(BaseModel):
    status: str           # approved | live | rejected | flagged | hidden
    admin_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    changes_requested_note: Optional[str] = None


@router.put("/listings/{property_id}/status")
async def update_listing_status(
    property_id: UUID,
    decision: ListingDecision,
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """
    Admin approves, rejects, flags, or hides a listing.
    Rejection and changes_requested decisions require a note.
    """
    allowed_statuses = ["live", "rejected", "flagged", "hidden",
                        "changes_requested", "archived"]
    if decision.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {allowed_statuses}"
        )

    # Rejections MUST have a reason — caretaker needs to know why
    if decision.status in ["rejected", "changes_requested"]:
        if not decision.admin_notes:
            raise HTTPException(
                status_code=400,
                detail="Rejection and change requests require admin notes"
            )

    result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    house = result.scalar_one_or_none()

    if house is None:
        raise HTTPException(status_code=404, detail="Property not found")

    house.status = decision.status
    house.admin_notes = decision.admin_notes
    house.rejection_reason = decision.rejection_reason
    house.changes_requested_note = decision.changes_requested_note
    house.reviewed_by = current_user["user_id"]
    house.reviewed_at = datetime.utcnow()

    await db.commit()

    return {
        "message": f"Listing status updated to '{decision.status}'",
        "property_id": str(property_id)
    }


# ════════════════════════════════════════════════════════════════
# REPORTS — Fraud queue from your Safety & Trust section
# ════════════════════════════════════════════════════════════════

@router.get("/reports")
async def get_reports(
    status: Optional[str] = "open",   # default: show open reports
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns fraud/issue reports.
    Your screenshot shows 6 open reports — this is what populates that badge.
    """
    query = select(Report)
    if status:
        query = query.where(Report.status == status)
    query = query.order_by(Report.created_at.desc())   # newest first

    result = await db.execute(query)
    return result.scalars().all()


class ReportResolution(BaseModel):
    status: str         # investigating | action_taken | dismissed | closed
    admin_notes: str    # required — what action was taken


@router.put("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: UUID,
    resolution: ReportResolution,
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """Admin resolves a fraud report."""
    result = await db.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    report.status = resolution.status
    report.admin_notes = resolution.admin_notes
    report.resolved_by = current_user["user_id"]
    report.updated_at = datetime.utcnow()

    await db.commit()

    return {"message": f"Report marked as '{resolution.status}'"}


# ════════════════════════════════════════════════════════════════
# REVIEWS — Moderation from Safety & Trust section
# ════════════════════════════════════════════════════════════════

@router.get("/reviews")
async def get_all_reviews(
    is_hidden: Optional[bool] = False,   # default: show visible reviews only
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """Returns reviews for admin moderation."""
    query = select(Review)
    if is_hidden is not None:
        query = query.where(Review.is_hidden == is_hidden)
    query = query.order_by(Review.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.put("/reviews/{review_id}/hide")
async def hide_review(
    review_id: UUID,
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """
    Admin hides an abusive or false review.
    We never delete reviews — hidden means invisible to public,
    but remains in the database for accountability.
    """
    result = await db.execute(
        select(Review).where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()

    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    review.is_hidden = True
    await db.commit()

    return {"message": "Review hidden from public view"}


# ════════════════════════════════════════════════════════════════
# CUSTOMERS — Customer management section
# ════════════════════════════════════════════════════════════════

@router.get("/customers")
async def list_customers(
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """Returns all customer profiles for admin management."""
    result = await db.execute(
        select(Profile).where(Profile.role == "customer")
        .order_by(Profile.created_at.desc())
    )
    return result.scalars().all()


# ════════════════════════════════════════════════════════════════
# APPOINTMENTS — Admin overview of all viewings
# ════════════════════════════════════════════════════════════════

@router.get("/appointments")
async def get_all_appointments(
    status: Optional[str] = None,
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db)
):
    """Returns all appointments. Admin sees everything."""
    query = select(Appointment)
    if status:
        query = query.where(Appointment.status == status)
    query = query.order_by(Appointment.preferred_date.desc())

    result = await db.execute(query)
    return result.scalars().all()