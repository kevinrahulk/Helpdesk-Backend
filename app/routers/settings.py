"""
System Settings API endpoints
GET  /settings           list all settings (any authenticated user)
PUT  /settings/{key}     update a setting (admin only)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import SystemSetting, User
from app.schemas import (
    APIResponse,
    CommentPermissionResponse,
    SystemSettingResponse,
    SystemSettingUpdate,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


def _get_setting(db: Session, key: str) -> SystemSetting | None:
    return db.query(SystemSetting).filter(SystemSetting.key == key).first()


def get_setting_value(db: Session, key: str, default: str = "true") -> str:
    """Get a setting value, returning default if not found."""
    setting = _get_setting(db, key)
    return setting.value if setting else default


@router.get("", response_model=APIResponse[list[SystemSettingResponse]])
def list_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all system settings."""
    settings = db.query(SystemSetting).all()
    return APIResponse(
        success=True,
        message="Settings fetched",
        data=[SystemSettingResponse.model_validate(s) for s in settings],
    )


@router.get("/comment-permissions", response_model=APIResponse[CommentPermissionResponse])
def get_comment_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Check if employee comments are enabled."""
    value = get_setting_value(db, "employee_comments_enabled", "true")
    return APIResponse(
        success=True,
        message="Comment permissions fetched",
        data=CommentPermissionResponse(
            employee_comments_enabled=value.lower() == "true",
        ),
    )


@router.put("/{key}", response_model=APIResponse[SystemSettingResponse])
def update_setting(
    key: str,
    payload: SystemSettingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Update a system setting. Admin only."""
    setting = _get_setting(db, key)
    if not setting:
        # Create it if it doesn't exist
        setting = SystemSetting(key=key, value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value

    db.commit()
    db.refresh(setting)
    return APIResponse(
        success=True,
        message=f"Setting '{key}' updated",
        data=SystemSettingResponse.model_validate(setting),
    )
