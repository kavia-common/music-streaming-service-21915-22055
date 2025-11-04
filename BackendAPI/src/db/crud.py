"""
CRUD and data-access helpers for BackendAPI.

Contains functions for:
- Auth and user management (registration, login, profile update)
- Playlist operations (create, update, delete, list, add/remove tracks)
- Catalog search helpers

All functions expect a SQLAlchemy Session (2.0 style).
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from sqlalchemy import and_, func, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.security import hash_password, verify_password, create_access_token
from src.db.models import (
    Album,
    Artist,
    Playlist,
    PlaylistTrack,
    Track,
    User,
)
from src.schemas.users import UserCreate, UserLogin, UserUpdate


# --------------------------
# Users / Auth
# --------------------------

# PUBLIC_INTERFACE
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email."""
    stmt = select(User).where(func.lower(User.email) == func.lower(email)).limit(1)
    return db.execute(stmt).scalars().first()


# PUBLIC_INTERFACE
def create_user(db: Session, data: UserCreate) -> Tuple[Optional[User], Optional[str]]:
    """Register a new user. Returns (user, error)."""
    try:
        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            display_name=data.display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, None
    except IntegrityError:
        db.rollback()
        return None, "Email already registered"
    except Exception as e:
        db.rollback()
        return None, str(e)


# PUBLIC_INTERFACE
def authenticate_user(db: Session, credentials: UserLogin) -> Tuple[Optional[str], Optional[User], Optional[str]]:
    """Authenticate user and return (token, user, error)."""
    user = get_user_by_email(db, credentials.email)
    if not user or not verify_password(credentials.password, user.password_hash):
        return None, None, "Invalid credentials"
    token = create_access_token(str(user.id), extra_claims={"email": user.email, "is_admin": user.is_admin})
    return token, user, None


# PUBLIC_INTERFACE
def update_user_profile(db: Session, user_id: int, updates: UserUpdate) -> Optional[User]:
    """Update user profile fields."""
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(
            **{k: v for k, v in updates.model_dump(exclude_unset=True).items()}
        )
        .returning(User)
    )
    result = db.execute(stmt)
    db.commit()
    row = result.first()
    return row[0] if row else None


# --------------------------
# Playlists
# --------------------------

# PUBLIC_INTERFACE
def list_user_playlists(db: Session, owner_user_id: int) -> List[Playlist]:
    """List playlists belonging to a user."""
    stmt = select(Playlist).where(Playlist.owner_user_id == owner_user_id).order_by(Playlist.created_at.desc())
    return list(db.execute(stmt).scalars().all())


# PUBLIC_INTERFACE
def create_playlist(
    db: Session, owner_user_id: int, name: str, description: Optional[str] = None, cover_image: Optional[str] = None, is_public: bool = False
) -> Tuple[Optional[Playlist], Optional[str]]:
    """Create a new playlist."""
    try:
        playlist = Playlist(
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            cover_image=cover_image,
            is_public=is_public,
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        return playlist, None
    except IntegrityError:
        db.rollback()
        return None, "Playlist name already exists for this user"
    except Exception as e:
        db.rollback()
        return None, str(e)


# PUBLIC_INTERFACE
def get_playlist(db: Session, playlist_id: int, owner_user_id: Optional[int] = None) -> Optional[Playlist]:
    """Fetch a playlist by id, optionally restricting to owner."""
    stmt = select(Playlist).where(Playlist.id == playlist_id)
    if owner_user_id is not None:
        stmt = stmt.where(Playlist.owner_user_id == owner_user_id)
    return db.execute(stmt).scalars().first()


# PUBLIC_INTERFACE
def update_playlist(
    db: Session, playlist_id: int, owner_user_id: int, name: Optional[str] = None, description: Optional[str] = None, cover_image: Optional[str] = None, is_public: Optional[bool] = None
) -> Optional[Playlist]:
    """Update editable fields on playlist."""
    values = {k: v for k, v in {
        "name": name,
        "description": description,
        "cover_image": cover_image,
        "is_public": is_public,
    }.items() if v is not None}
    stmt = (
        update(Playlist)
        .where(and_(Playlist.id == playlist_id, Playlist.owner_user_id == owner_user_id))
        .values(**values)
        .returning(Playlist)
    )
    result = db.execute(stmt)
    db.commit()
    row = result.first()
    return row[0] if row else None


# PUBLIC_INTERFACE
def delete_playlist(db: Session, playlist_id: int, owner_user_id: int) -> bool:
    """Delete a playlist by id for the owner."""
    stmt = delete(Playlist).where(and_(Playlist.id == playlist_id, Playlist.owner_user_id == owner_user_id))
    res = db.execute(stmt)
    db.commit()
    return res.rowcount > 0


# PUBLIC_INTERFACE
def list_playlist_tracks(db: Session, playlist_id: int) -> List[PlaylistTrack]:
    """List tracks in a playlist ordered by position."""
    stmt = select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id).order_by(PlaylistTrack.position.asc())
    return list(db.execute(stmt).scalars().all())


# PUBLIC_INTERFACE
def add_track_to_playlist(db: Session, playlist_id: int, track_id: int, position: Optional[int] = None) -> Tuple[Optional[PlaylistTrack], Optional[str]]:
    """Add a track to a playlist at a position (append if not provided)."""
    try:
        if position is None:
            # find max position
            last_pos_stmt = select(func.coalesce(func.max(PlaylistTrack.position), -1)).where(PlaylistTrack.playlist_id == playlist_id)
            last_pos = db.execute(last_pos_stmt).scalar_one()
            position = int(last_pos) + 1
        link = PlaylistTrack(playlist_id=playlist_id, track_id=track_id, position=position)
        db.add(link)
        db.commit()
        db.refresh(link)
        return link, None
    except IntegrityError:
        db.rollback()
        return None, "Track already in playlist"
    except Exception as e:
        db.rollback()
        return None, str(e)


# PUBLIC_INTERFACE
def remove_track_from_playlist(db: Session, playlist_id: int, track_id: int) -> bool:
    """Remove a track from a playlist."""
    stmt = delete(PlaylistTrack).where(
        and_(PlaylistTrack.playlist_id == playlist_id, PlaylistTrack.track_id == track_id)
    )
    res = db.execute(stmt)
    db.commit()
    return res.rowcount > 0


# --------------------------
# Catalog helpers (search)
# --------------------------

# PUBLIC_INTERFACE
def search_catalog(
    db: Session, query: str, genre: Optional[str] = None, artist: Optional[str] = None, album: Optional[str] = None, limit: int = 25, offset: int = 0
) -> dict[str, list[Any]]:
    """Search tracks, artists, and albums by text and filters.

    Returns a dict with keys: tracks, artists, albums.
    """
    q_like = f"%{query.lower()}%" if query else None

    # Artists
    artist_stmt = select(Artist).limit(limit).offset(offset)
    if q_like:
        artist_stmt = artist_stmt.where(func.lower(Artist.name).like(q_like))
    if artist:
        artist_stmt = artist_stmt.where(func.lower(Artist.name) == artist.lower())
    artists = list(db.execute(artist_stmt).scalars().all())

    # Albums
    album_stmt = select(Album).limit(limit).offset(offset)
    if q_like:
        album_stmt = album_stmt.where(func.lower(Album.title).like(q_like))
    if album:
        album_stmt = album_stmt.where(func.lower(Album.title) == album.lower())
    albums = list(db.execute(album_stmt).scalars().all())

    # Tracks
    track_stmt = select(Track).limit(limit).offset(offset)
    filters = []
    if q_like:
        filters.append(func.lower(Track.title).like(q_like))
    if genre:
        filters.append(func.lower(Track.genre) == genre.lower())
    if artist:
        # join via artist_id by subquery matching artist name
        artist_ids_stmt = select(Artist.id).where(func.lower(Artist.name) == artist.lower())
        track_stmt = track_stmt.where(Track.artist_id.in_(artist_ids_stmt))
    if album:
        album_ids_stmt = select(Album.id).where(func.lower(Album.title) == album.lower())
        track_stmt = track_stmt.where(Track.album_id.in_(album_ids_stmt))
    if filters:
        track_stmt = track_stmt.where(and_(*filters))
    tracks = list(db.execute(track_stmt).scalars().all())

    return {
        "artists": artists,
        "albums": albums,
        "tracks": tracks,
    }
