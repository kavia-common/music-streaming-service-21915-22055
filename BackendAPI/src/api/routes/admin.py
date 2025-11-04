"""
Admin routes: user management and catalog administration with audit logging.

Exposes:
- GET /admin/users: Paginated list of users (admin-only)
- POST /admin/music: Create a new track (admin-only)

On each admin action, insert a row into admin_audit_logs with:
- actor (admin_user_id)
- action (string)
- target_type (e.g., "user" or "track")
- target_id (string id if applicable)
- details (diff/payload info)
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.deps import get_current_admin, get_db
from src.db.models import AdminAuditLog, Track, User
from src.schemas.catalog import TrackCreate, TrackOut
from src.schemas.users import UserOut

router = APIRouter(prefix="/admin", tags=["Admin"])


def _audit(
    db: Session,
    admin_user_id: int,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """
    Insert a row into admin_audit_logs. Errors are swallowed to not block main flow.
    """
    try:
        log = AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
        # Intentionally ignore audit failures


@router.get(
    "/users",
    summary="List users (admin)",
    response_model=List[UserOut],
    responses={
        200: {"description": "User list"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    },
)
def list_users_admin(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
) -> List[UserOut]:
    """
    Return a paginated list of users.

    Parameters:
    - page: pagination page (1-indexed)
    - limit: items per page (max 100)

    Returns:
    - List[UserOut]
    """
    offset = (page - 1) * limit
    stmt = (
        select(User)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = list(db.execute(stmt).scalars().all())

    # Fire-and-forget audit log
    _audit(
        db=db,
        admin_user_id=current_admin.id,
        action="admin.list_users",
        target_type="user",
        target_id=None,
        details={"page": page, "limit": limit, "count": len(users)},
    )

    return [UserOut.model_validate(u) for u in users]


def _create_track(
    db: Session, payload: TrackCreate
) -> Tuple[Optional[Track], Optional[str]]:
    """
    Create a track from TrackCreate payload. Returns (track, error).
    """
    try:
        track = Track(
            title=payload.title,
            artist_id=payload.artist_id,
            album_id=payload.album_id,
            genre=payload.genre,
            duration_seconds=payload.duration_seconds,
            audio_url=payload.audio_url,
        )
        db.add(track)
        db.commit()
        db.refresh(track)
        return track, None
    except IntegrityError:
        db.rollback()
        # Attempt to guess common causes (e.g., bad FK)
        return None, "Integrity error creating track"
    except Exception as exc:
        db.rollback()
        return None, str(exc)


@router.post(
    "/music",
    summary="Create a new track (admin)",
    response_model=TrackOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Track created"},
        400: {"description": "Validation or persistence error"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    },
)
def create_music_admin(
    payload: TrackCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> TrackOut:
    """
    Create a new track in the catalog.

    Parameters:
    - payload: TrackCreate (title, artist_id, optional album_id, genre, duration_seconds, audio_url)

    Returns:
    - TrackOut of the created track
    """
    track, err = _create_track(db, payload)
    if err or not track:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Unable to create track")

    # Audit the creation with a minimal "diff" stored in details
    _audit(
        db=db,
        admin_user_id=current_admin.id,
        action="admin.create_track",
        target_type="track",
        target_id=str(track.id),
        details={
            "payload": {
                "title": payload.title,
                "artist_id": payload.artist_id,
                "album_id": payload.album_id,
                "genre": payload.genre,
                "duration_seconds": payload.duration_seconds,
                "audio_url": payload.audio_url,
            }
        },
    )

    return TrackOut.model_validate(track)
