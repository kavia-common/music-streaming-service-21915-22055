"""
SQLAlchemy ORM models for the BackendAPI service.

This module defines core database tables:
- users
- artists
- albums
- tracks
- playlists
- playlist_tracks (association)
- playback_history
- user_activity
- admin_audit_logs
- recommendations_cache

The definitions are designed to align with a typical normalized schema for a music streaming service
backed by PostgreSQL. All timestamps are in UTC, and sensible indexes/uniqueness constraints are used.

Note: If Database/schema.sql differs, sync constraints/fields accordingly.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    CheckConstraint,

    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for ORM models."""

    # helpful for Alembic and metadata naming
    pass


# USERS
class User(Base):
    """Platform user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    notification_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    playlists: Mapped[List["Playlist"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    playback_history: Mapped[List["PlaybackHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    activities: Mapped[List["UserActivity"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    admin_audits: Mapped[List["AdminAuditLog"]] = relationship(
        back_populates="admin", cascade="all, delete-orphan", foreign_keys="AdminAuditLog.admin_user_id"
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
    )


# ARTISTS
class Artist(Base):
    """Music artist."""

    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    albums: Mapped[List["Album"]] = relationship(back_populates="artist", cascade="all, delete-orphan")
    tracks: Mapped[List["Track"]] = relationship(back_populates="artist")

    __table_args__ = (
        UniqueConstraint("name", name="uq_artists_name"),
        Index("ix_artists_name", "name"),
    )


# ALBUMS
class Album(Base):
    """Album contains one or more tracks and belongs to an artist."""

    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), nullable=False)
    release_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cover_image: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    artist: Mapped["Artist"] = relationship(back_populates="albums")
    tracks: Mapped[List["Track"]] = relationship(back_populates="album", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("title", "artist_id", name="uq_albums_title_artist"),
        Index("ix_albums_title", "title"),
    )


# TRACKS
class Track(Base):
    """A track (song) that belongs to an artist and optionally an album."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="RESTRICT"), nullable=False)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("albums.id", ondelete="SET NULL"), nullable=True)
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    audio_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    artist: Mapped["Artist"] = relationship(back_populates="tracks")
    album: Mapped[Optional["Album"]] = relationship(back_populates="tracks")
    playlist_links: Mapped[List["PlaylistTrack"]] = relationship(back_populates="track", cascade="all, delete-orphan")
    playback_history: Mapped[List["PlaybackHistory"]] = relationship(back_populates="track", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tracks_title", "title"),
        Index("ix_tracks_genre", "genre"),
        CheckConstraint("duration_seconds > 0", name="ck_tracks_duration_positive"),
    )


# PLAYLISTS
class Playlist(Base):
    """User-owned playlist."""

    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_image: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="playlists")
    tracks: Mapped[List["PlaylistTrack"]] = relationship(back_populates="playlist", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_playlists_owner_name"),
        Index("ix_playlists_owner", "owner_user_id"),
        Index("ix_playlists_is_public", "is_public"),
    )


# PLAYLIST_TRACKS association
class PlaylistTrack(Base):
    """Association table between playlists and tracks with track order."""

    __tablename__ = "playlist_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    playlist: Mapped["Playlist"] = relationship(back_populates="tracks")
    track: Mapped["Track"] = relationship(back_populates="playlist_links")

    __table_args__ = (
        UniqueConstraint("playlist_id", "track_id", name="uq_playlist_track_unique"),
        Index("ix_playlist_tracks_playlist_position", "playlist_id", "position"),
        CheckConstraint("position >= 0", name="ck_playlist_tracks_position_nonnegative"),
    )


# PLAYBACK HISTORY
class PlaybackHistory(Base):
    """Tracks playback events per user."""

    __tablename__ = "playback_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    played_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship(back_populates="playback_history")
    track: Mapped["Track"] = relationship(back_populates="playback_history")

    __table_args__ = (
        Index("ix_playback_history_user_played_at", "user_id", "played_at"),
        CheckConstraint("duration_seconds >= 0", name="ck_playback_history_duration_nonnegative"),
    )


# USER ACTIVITY
class UserActivity(Base):
    """Arbitrary user actions for analytics/auditing."""

    __tablename__ = "user_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    user: Mapped["User"] = relationship(back_populates="activities")

    __table_args__ = (
        Index("ix_user_activity_user_action", "user_id", "action"),
    )


# ADMIN AUDIT LOGS
class AdminAuditLog(Base):
    """Audit logs for admin actions."""

    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(150), nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    admin: Mapped[Optional["User"]] = relationship(back_populates="admin_audits", foreign_keys=[admin_user_id])

    __table_args__ = (
        Index("ix_admin_audit_action", "action"),
    )


# RECOMMENDATIONS CACHE
class RecommendationsCache(Base):
    """Cached recommendations per user for fast retrieval."""

    __tablename__ = "recommendations_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    # Store a list of recommended track IDs and optional scores/metadata
    recommendations: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_recommendations_user"),
    )
