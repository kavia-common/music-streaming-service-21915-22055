"""
Authentication routes: registration and login.

Exposes:
- POST /auth/register: Register a new user account
- POST /auth/login: Authenticate and return an access token plus profile

Responses align with frontend expectations:
- On success returns { "access_token": "<jwt>", "user": {<profile>} }
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.db.crud import create_user, authenticate_user, get_user_by_email
from src.schemas.users import UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    summary="Register a new user",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User registered"},
        400: {"description": "Validation error"},
        409: {"description": "Email already registered"},
    },
)
def register(data: UserCreate, db: Session = Depends(get_db)) -> dict:
    """
    Register a new user.

    Parameters:
    - data: UserCreate payload with email, password, optional display_name

    Returns:
    - JSON containing access_token and user profile on success:
      { "access_token": "<jwt>", "user": { ...UserOut } }

    Raises:
    - 409 if email already registered
    - 400 for other validation/database errors
    """
    # quick check to give clearer 409
    existing = get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user, err = create_user(db, data)
    if err or not user:
        # Integrity errors are handled above; other issues treated as 400
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Unable to register user")

    # Auto-login after registration for smoother UX
    token, _, auth_err = authenticate_user(db, UserLogin(email=data.email, password=data.password))
    if auth_err or not token:
        # If token creation failed (unlikely), still return created without token
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create access token")

    user_out = UserOut.model_validate(user)
    return {"access_token": token, "user": user_out.model_dump()}


@router.post(
    "/login",
    summary="User login",
    response_model=dict,
    responses={
        200: {"description": "JWT token and user profile"},
        401: {"description": "Invalid credentials"},
    },
)
def login(credentials: UserLogin, db: Session = Depends(get_db)) -> dict:
    """
    Authenticate a user and return an access token with profile.

    Parameters:
    - credentials: UserLogin with email and password

    Returns:
    - { "access_token": "<jwt>", "user": { ...UserOut } }

    Raises:
    - 401 for invalid credentials
    """
    token, user, err = authenticate_user(db, credentials)
    if err or not token or not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user_out = UserOut.model_validate(user)
    return {"access_token": token, "user": user_out.model_dump()}
