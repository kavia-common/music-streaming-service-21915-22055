"""
Streaming routes: start and stop streaming sessions.

Exposes:
- POST /stream/start: Start a streaming session for an authenticated user
- POST /stream/stop: Stop a streaming session and record playback duration

Both routes require authentication (Bearer token) and use the database to persist playback events.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.db.models import User as UserModel
from src.schemas.streaming import (
    StreamStartRequest,
    StreamStartResponse,
    StreamStopRequest,
)
from src.services.streaming import start_streaming_session, stop_streaming_session

router = APIRouter(prefix="/stream", tags=["Catalog"])


@router.post(
    "/start",
    summary="Start music stream",
    response_model=StreamStartResponse,
    responses={
        200: {"description": "Streaming session started"},
        400: {"description": "Validation error"},
        401: {"description": "Unauthorized"},
        404: {"description": "Not found"},
    },
)
def start_stream(
    payload: StreamStartRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> StreamStartResponse:
    """
    Start a streaming session for the current user.

    Parameters:
    - track_id: Track identifier to stream.

    Returns:
    - StreamStartResponse including the stream_url to be used by the client player.

    Raises:
    - 404 if the track does not exist.
    - 400 if the track is not streamable (missing audio_url) or persistence fails.
    """
    session, err = start_streaming_session(db, user_id=current_user.id, track_id=payload.track_id)
    if err:
        if "not found" in err.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    if not session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to start stream")

    return StreamStartResponse(
        track_id=session.track_id,
        stream_url=session.stream_url,
        started_at=session.started_at,
    )


@router.post(
    "/stop",
    summary="Stop music stream",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Streaming session stopped"},
        400: {"description": "Validation or persistence error"},
        401: {"description": "Unauthorized"},
    },
)
def stop_stream(
    payload: StreamStopRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> dict:
    """
    Stop a streaming session for the current user.

    Parameters:
    - track_id: Track being streamed.
    - played_seconds: Optional actual played time reported by the client.

    Returns:
    - { "status": "stopped" }
    """
    ok, err = stop_streaming_session(
        db,
        user_id=current_user.id,
        track_id=payload.track_id,
        played_seconds=payload.played_seconds,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Unable to stop stream")
    return {"status": "stopped"}
