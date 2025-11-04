"""
Pydantic schemas for user authentication and profile.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="Unique email for the user")
    display_name: Optional[str] = Field(None, description="Public display name")
    is_active: Optional[bool] = Field(default=True, description="Whether the user is active")
    is_admin: Optional[bool] = Field(default=False, description="Whether the user is an administrator")
    notification_settings: Optional[dict[str, Any]] = Field(default=None, description="Notification preferences")


class UserCreate(BaseModel):
    email: EmailStr = Field(..., description="Unique email for the user")
    password: str = Field(..., min_length=6, description="Plain password for registration")
    display_name: Optional[str] = Field(None, description="Public display name")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, description="Public display name")
    notification_settings: Optional[dict[str, Any]] = Field(default=None, description="Notification preferences")


class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
