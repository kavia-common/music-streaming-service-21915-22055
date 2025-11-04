"""
Pydantic schemas for catalog entities: artists, albums, tracks, and search parameters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ArtistBase(BaseModel):
    name: str = Field(..., description="Artist name")
    bio: Optional[str] = Field(None, description="Biography text")


class ArtistCreate(ArtistBase):
    """Create schema for artist."""


class ArtistOut(ArtistBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlbumBase(BaseModel):
    title: str = Field(..., description="Album title")
    artist_id: int = Field(..., description="Related artist id")
    release_year: Optional[int] = Field(None, description="Year of release")
    cover_image: Optional[str] = Field(None, description="Cover image URL")


class AlbumCreate(AlbumBase):
    """Create schema for album."""


class AlbumOut(AlbumBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrackBase(BaseModel):
    title: str = Field(..., description="Track title")
    artist_id: int = Field(..., description="Related artist id")
    album_id: Optional[int] = Field(None, description="Related album id")
    genre: Optional[str] = Field(None, description="Genre label")
    duration_seconds: int = Field(..., ge=1, description="Duration in seconds")
    audio_url: Optional[str] = Field(None, description="Audio URL for streaming")


class TrackCreate(TrackBase):
    """Create schema for track."""


class TrackOut(TrackBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CatalogSearchParams(BaseModel):
    query: str = Field(..., description="Search query term")
    genre: Optional[str] = Field(None, description="Optional genre filter")
    artist: Optional[str] = Field(None, description="Optional artist filter (name)")
    album: Optional[str] = Field(None, description="Optional album filter (title)")
