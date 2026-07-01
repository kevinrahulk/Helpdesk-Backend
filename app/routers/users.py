"""
User Management (Admin only)
Endpoints:
  GET    /users                 list with filters
  POST   /users                 create employee
  POST   /agents                create agent
  GET    /users/{id}            fetch single user
  PUT    /users/{id}            update user
  PATCH  /users/{id}/status     activate / deactivate
  GET    /agents                list agents with workload
"""

from typing import Optional
from uuid import UUID

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Query, status
# pyrefly: ignore [missing-import]
from sqlalchemy import func
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.auth import get_current_user, hash_password, require_admin
from app.database import get_db
from app.models import RoleNameEnum, Ticket, TicketStatusEnum, User, Role
from app.schemas import (
    AgentWorkload,
    APIResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)

router = APIRouter(tags=["Users"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _get_role_by_name(db: Session, name: RoleNameEnum) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Role '{name.value}' not seeded in database.",
        )
    return role


def _build_user(db: Session, payload: UserCreate, role_override: Optional[RoleNameEnum] = None) -> User:
    """Validate uniqueness and build User ORM object."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )
    # role_id from payload unless overridden
    if role_override:
        role = _get_role_by_name(db, role_override)
        role_id = role.id
    else:
        role_id = payload.role_id
        role = db.get(Role, role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role_id.")

    return User(
        role_id=role_id,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/users", response_model=APIResponse[UserListResponse])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None, description="Filter by role: employee | agent | admin"),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search by name or email"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """List all users with optional filters. Admin only."""
    q = db.query(User)

    if role:
        try:
            role_enum = RoleNameEnum(role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
        q = q.join(User.role).filter(Role.name == role_enum)

    if is_active is not None:
        q = q.filter(User.is_active == is_active)

    if search:
        like = f"%{search}%"
        q = q.filter((User.full_name.ilike(like)) | (User.email.ilike(like)))

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return APIResponse(
        success=True,
        message="Users fetched",
        data=UserListResponse(
            items=[UserResponse.model_validate(u) for u in items],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.post("/users", response_model=APIResponse[UserResponse], status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = _build_user(db, payload, role_override=RoleNameEnum.employee)
    db.add(user)
    db.commit()
    db.refresh(user)
    return APIResponse(success=True, message="Employee created", data=UserResponse.model_validate(user))


@router.post("/agents", response_model=APIResponse[UserResponse], status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = _build_user(db, payload, role_override=RoleNameEnum.agent)
    db.add(user)
    db.commit()
    db.refresh(user)
    return APIResponse(success=True, message="Agent created", data=UserResponse.model_validate(user))


"""Return all active agents with their current open ticket count. Admin only."""
@router.get("/agents", response_model=APIResponse[list[AgentWorkload]])
def list_agents(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    agent_role = _get_role_by_name(db, RoleNameEnum.agent)
    agents = (db.query(User).filter(User.role_id == agent_role.id, User.is_active == True).all())

    workload = []
    for agent in agents:
        open_count = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.assigned_to == agent.id,
                Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
            )
            .scalar()
        )
        workload.append(
            AgentWorkload(
                id=agent.id,
                full_name=agent.full_name,
                email=agent.email,
                open_ticket_count=open_count or 0,
            )
        )

    return APIResponse(success=True, message="Agent workload fetched", data=workload)


@router.get("/users/{user_id}", response_model=APIResponse[UserResponse])
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch a single user.
    - Admin: any user
    - Others: only own profile
    """
    if current_user.role.name != RoleNameEnum.admin and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return APIResponse(success=True, message="User fetched", data=UserResponse.model_validate(user))


@router.put("/users/{user_id}", response_model=APIResponse[UserResponse])
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Update user details. Admin only."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if payload.email and payload.email != user.email:
        dup = db.query(User).filter(User.email == payload.email).first()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use.")
        user.email = payload.email

    if payload.full_name:
        user.full_name = payload.full_name

    if payload.role_id:
        role = db.get(Role, payload.role_id)
        if not role:
            raise HTTPException(status_code=400, detail="Invalid role_id.")
        user.role_id = payload.role_id

    db.commit()
    db.refresh(user)
    return APIResponse(success=True, message="User updated", data=UserResponse.model_validate(user))


@router.patch("/users/{user_id}/status", response_model=APIResponse[UserResponse])
def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Activate or deactivate a user account. Admin only."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)

    action = "activated" if payload.is_active else "deactivated"
    return APIResponse(success=True, message=f"User {action}", data=UserResponse.model_validate(user))
