"""
Pydantic schemas for playlist operations and responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PlaylistBase(BaseModel):
    name: str = Field(..., description="Playlist name")
    description: Optional[str] = Field(None, description="Playlist description")
    cover_image: Optional[str] = Field(None, description="Cover image URL")
    is_public: Optional[bool] = Field(default=False, description="Whether the playlist is public")


class PlaylistCreate(PlaylistBase):
    """Create schema for playlist."""


class PlaylistUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Playlist name")
    description: Optional[str] = Field(None, description="Playlist description")
    cover_image: Optional[str] = Field(None, description="Cover image URL")
    is_public: Optional[bool] = Field(None, description="Whether the playlist is public")


class PlaylistTrackItem(BaseModel):
    track_id: int
    position: int


class PlaylistOut(PlaylistBase):
    id: int
    owner_user_id: int
    created_at: datetime
    updated_at: datetime
    tracks: List[PlaylistTrackItem] = Field(default_factory=list)

    class Config:
        from_attributes = True
