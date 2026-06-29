"""
Module 1 — Authentication
Endpoints: POST /auth/login · POST /auth/logout · GET /auth/profile
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import (
    APIResponse,
    AuthData,
    LoginRequest,
    LoginResponse,
    UserResponse,
    UserSummary,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return a JWT access token.

    - Validates email existence and password hash
    - Rejects deactivated accounts
    - Returns token + user profile (id, name, role)
    """
    # 1. Look up user by email
    user: User | None = (
        db.query(User)
        .filter(User.email == payload.email)
        .first()
    )

    # 2. Validate credentials (same error message for security)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 3. Check active status
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Please contact admin.",
        )

    # 4. Issue JWT
    token, expires_in = create_access_token(
        subject=str(user.id),
        role=user.role.name.value,
    )

    user_summary = UserSummary(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name.value,
    )

    return LoginResponse(
        success=True,
        message="Login Successful",
        data=AuthData(access_token=token, user=user_summary),
    )


@router.post("/logout", response_model=APIResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint.
    JWT is stateless — client must discard the token.
    Returns a confirmation message.
    """
    return APIResponse(success=True, message="Logged out successfully")


@router.get("/profile", response_model=APIResponse[UserResponse])
def get_profile(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's full profile."""
    return APIResponse(
        success=True,
        message="Profile fetched",
        data=UserResponse.model_validate(current_user),
    )
