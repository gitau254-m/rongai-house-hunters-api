from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.core.debs import get_current_user
from app.models.notification import Notification

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str  # e.g. "appointment_confirmed", "listing_approved"
    title: str  # e.g. "Your viewing is confirmed!"
    message: str  # full text
    link: Optional[str] = None  # where to go when clicked
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[NotificationResponse])
async def get_my_notifications(
        # Optional filter — show only unread, or all
        unread_only: bool = False,
        # Any logged-in user can get their notifications
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Returns this user's notifications.
    Powers the bell icon dropdown in the navbar.
    The unread_only=true filter powers the badge count.
    """
    query = select(Notification).where(
        Notification.user_id == current_user["user_id"]
    )

    # If they only want unread notifications (for the badge count)
    if unread_only:
        query = query.where(Notification.is_read == False)

    # Most recent first — newest at top of dropdown
    query = query.order_by(Notification.created_at.desc()).limit(50)

    result = await db.execute(query)
    return result.scalars().all()

@router.put("/read-all")
async def mark_all_notifications_read(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Marks ALL of this user's notifications as read at once.
    Powers the "Mark all as read" button in the bell dropdown.
    """

    # This is more efficient than fetching every notification and
    # looping through them — one UPDATE statement touches all rows at once
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user["user_id"],
            Notification.is_read == False  # only update unread ones
        )
        .values(is_read=True)
    )

    await db.commit()
    return {"message": "All notifications marked as read"}


@router.put("/{notification_id}/read")
async def mark_notification_read(
        notification_id: UUID,
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Marks one notification as read.
    Called when the user clicks on a notification in the dropdown.
    """
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            # Security: you can only mark YOUR OWN notifications as read
            Notification.user_id == current_user["user_id"]
        )
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    await db.commit()

    return {"message": "Marked as read"}




# ── Helper function (used by other routers to CREATE notifications) ──
# Not an endpoint — a utility function your code calls internally.
# For example, when an appointment is confirmed, appointments.py calls this.
async def create_notification(
        db: AsyncSession,
        user_id: str,
        type: str,
        title: str,
        message: str,
        link: Optional[str] = None
) -> None:
    """
    Creates a notification for a user.
    Called internally by other routers — not a public API endpoint.

    Usage example:
        await create_notification(
            db=db,
            user_id=customer_id,
            type="appointment_confirmed",
            title="Viewing confirmed!",
            message="Your viewing for Bedsitter near Naivas is confirmed for July 15.",
            link=f"/dashboard/customer/appointments/{appointment_id}"
        )
    """
    from uuid import uuid4
    notification = Notification(
        id=uuid4(),
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        link=link,
        is_read=False,
    )
    db.add(notification)
    # Note: no commit here — the calling function handles the commit
    # This keeps everything in one database transaction