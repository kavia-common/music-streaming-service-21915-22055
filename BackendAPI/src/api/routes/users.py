"""
User profile routes for the authenticated user.

Exposes:
- GET /users/me: Return current user's profile
- PATCH /users/me: Update current user's profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.db.crud import update_user_profile
from src.db.models import User as UserModel
from src.schemas.users import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["Auth"])


@router.get(
    "/me",
    summary="Get current user profile",
    response_model=UserOut,
    responses={
        200: {"description": "User profile"},
        401: {"description": "Unauthorized"},
    },
)
def read_current_user(
    current_user: UserModel = Depends(get_current_user),
) -> UserOut:
    """
    Return the current authenticated user's profile.
    """
    return UserOut.model_validate(current_user)


@router.patch(
    "/me",
    summary="Update current user profile",
    response_model=UserOut,
    responses={
        200: {"description": "Profile updated"},
        400: {"description": "Validation error"},
        401: {"description": "Unauthorized"},
    },
)
def update_me(
    updates: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> UserOut:
    """
    Update editable fields on the current user's profile.

    Parameters:
    - updates: partial update of display_name and/or notification_settings

    Returns:
    - Updated UserOut
    """
    updated = update_user_profile(db, user_id=current_user.id, updates=updates)
    if not updated:
        # If no row updated, treat as bad request (no changes)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes applied")
    return UserOut.model_validate(updated)
