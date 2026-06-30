"""
Ticket Categories — Admin managed, read-accessible to all authenticated users.
GET    /categories          list active categories
POST   /categories          create (admin)
GET    /categories/{id}     single category
PUT    /categories/{id}     update (admin)
DELETE /categories/{id}     soft-delete via is_active=False (admin)
"""

from uuid import UUID

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Query, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import TicketCategory, User
from app.schemas import (
    APIResponse,
    TicketCategoryCreate,
    TicketCategoryResponse,
    TicketCategoryUpdate,
)

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=APIResponse[list[TicketCategoryResponse]])
def list_categories(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return ticket categories. Defaults to active only."""
    q = db.query(TicketCategory)
    if active_only:
        q = q.filter(TicketCategory.is_active == True)
    categories = q.order_by(TicketCategory.name).all()
    return APIResponse(
        success=True,
        message="Categories fetched",
        data=[TicketCategoryResponse.model_validate(c) for c in categories],
    )


@router.post("", response_model=APIResponse[TicketCategoryResponse], status_code=status.HTTP_201_CREATED)
def create_category(
    payload: TicketCategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Create a new ticket category. Admin only."""
    existing = db.query(TicketCategory).filter(TicketCategory.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category name already exists.")

    cat = TicketCategory(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return APIResponse(success=True, message="Category created", data=TicketCategoryResponse.model_validate(cat))


@router.get("/{category_id}", response_model=APIResponse[TicketCategoryResponse])
def get_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cat = db.get(TicketCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    return APIResponse(success=True, message="Category fetched", data=TicketCategoryResponse.model_validate(cat))


@router.put("/{category_id}", response_model=APIResponse[TicketCategoryResponse])
def update_category(
    category_id: UUID,
    payload: TicketCategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    cat = db.get(TicketCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")

    if payload.name and payload.name != cat.name:
        dup = db.query(TicketCategory).filter(TicketCategory.name == payload.name).first()
        if dup:
            raise HTTPException(status_code=409, detail="Category name already exists.")
        cat.name = payload.name

    if payload.description is not None:
        cat.description = payload.description
    if payload.is_active is not None:
        cat.is_active = payload.is_active

    db.commit()
    db.refresh(cat)
    return APIResponse(success=True, message="Category updated", data=TicketCategoryResponse.model_validate(cat))


@router.delete("/{category_id}", response_model=APIResponse)
def deactivate_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Soft-delete a category by setting is_active=False. Admin only."""
    cat = db.get(TicketCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    cat.is_active = False
    db.commit()
    return APIResponse(success=True, message="Category deactivated")
