"""
FastAPI dependencies for database and authentication.

Provides:
- get_db: database session dependency
- get_current_user: extracts and validates JWT Bearer token, loads current user
- get_current_admin: ensures current user is an admin

Uses JWT utilities from src.core.security and models from src.db.
"""

from __future__ import annotations

from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.security import decode_token
from src.db.session import get_db as _get_db
from src.db.models import User
from src.db.crud import get_user_by_email

security_scheme = HTTPBearer(auto_error=False)


# PUBLIC_INTERFACE
def get_db() -> Generator:
    """Yield a database session for the request lifecycle."""
    yield from _get_db()


# PUBLIC_INTERFACE
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the current authenticated user from the Authorization: Bearer token.

    - Parses JWT with src.core.security.decode_token
    - Loads user via 'sub' or 'email' claims.
    - Validates user is active.

    Raises:
    - 401 if token missing/invalid
    - 401 if user not found/inactive
    """
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Prefer subject as user id; fallback to email if provided
    user: Optional[User] = None
    sub = payload.get("sub")
    email = payload.get("email")

    if sub is not None:
        # sub may be user id; attempt to query by id
        try:
            user_id = int(sub)
        except (TypeError, ValueError):
            user_id = None
        if user_id is not None:
            user = db.get(User, user_id)

    if user is None and email:
        user = get_user_by_email(db, email)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# PUBLIC_INTERFACE
def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensure the current user has administrative privileges.

    Raises:
    - 403 Forbidden if the user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user
