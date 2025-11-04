"""
Security utilities for the BackendAPI service.

Provides password hashing/verification using bcrypt and JWT token encode/decode
using the configured HS256 algorithm.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt  # PyJWT

from src.core.config import get_settings


# PUBLIC_INTERFACE
def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    if not isinstance(plain_password, str) or not plain_password:
        raise ValueError("Password must be a non-empty string")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


# PUBLIC_INTERFACE
def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not (plain_password and password_hash):
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# PUBLIC_INTERFACE
def create_access_token(subject: str, expires_delta: Optional[timedelta] = None, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """Create a signed JWT access token.

    Parameters:
    - subject: The token subject (e.g., user id or email).
    - expires_delta: Optional timedelta for expiration; falls back to configured minutes.
    - extra_claims: Optional additional JWT claims to include.

    Returns:
    - Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    # PyJWT returns str on modern versions
    return token


# PUBLIC_INTERFACE
def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token, returning the payload claims.

    Raises:
    - jwt.ExpiredSignatureError if the token is expired
    - jwt.InvalidTokenError for any other token issues
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    return payload
