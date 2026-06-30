"""
Notifications API endpoints
GET    /notifications              list notifications for current user
GET    /notifications/unread-count unread count for badge
PATCH  /notifications/{id}/read   mark single notification as read
PATCH  /notifications/mark-all-read  mark all as read
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Notification, User
from app.schemas import (
    APIResponse,
    NotificationListResponse,
    NotificationResponse,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=APIResponse[NotificationListResponse])
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notifications for the authenticated user, newest first."""
    base = db.query(Notification).filter(Notification.user_id == current_user.id)
    total = base.count()
    unread = base.filter(Notification.is_read == False).count()

    items = (
        base.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return APIResponse(
        success=True,
        message="Notifications fetched",
        data=NotificationListResponse(
            items=[NotificationResponse.model_validate(n) for n in items],
            total=total,
            unread_count=unread,
        ),
    )


@router.get("/unread-count", response_model=APIResponse[dict])
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the number of unread notifications for badge display."""
    count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .scalar() or 0
    )
    return APIResponse(
        success=True,
        message="Unread count fetched",
        data={"unread_count": count},
    )


@router.patch("/{notification_id}/read", response_model=APIResponse[NotificationResponse])
def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    notif = db.get(Notification, notification_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found.")

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return APIResponse(
        success=True,
        message="Marked as read",
        data=NotificationResponse.model_validate(notif),
    )


@router.patch("/mark-all-read", response_model=APIResponse)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read for the current user."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return APIResponse(success=True, message="All notifications marked as read")
