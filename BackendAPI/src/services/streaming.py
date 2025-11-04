"""
Streaming service for BackendAPI.

Provides functions to orchestrate starting and stopping a streaming session.
- When starting: verifies track exists and has an audio URL, records a playback start event,
  and returns a simple session payload including the stream_url.
- When stopping: records a playback stop event with played duration (best-effort).

This module persists activity to the PlaybackHistory table as simple events.
A more advanced implementation could have a dedicated sessions table; for now, we log
start and stop as separate history records to keep analytics and recommendations updated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PlaybackHistory, Track


@dataclass
class StreamSession:
    """Lightweight representation of a streaming session returned to the client."""
    user_id: int
    track_id: int
    stream_url: str
    started_at: datetime


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# PUBLIC_INTERFACE
def start_streaming_session(db: Session, user_id: int, track_id: int) -> Tuple[Optional[StreamSession], Optional[str]]:
    """
    Start a streaming session for a given user and track.

    Behavior:
    - Validates the track exists and has an audio_url.
    - Persists a PlaybackHistory row with duration_seconds = 0 as a 'start' marker.
    - Returns a StreamSession containing the resolved stream_url.

    Returns:
    - (StreamSession, None) on success
    - (None, "error message") on failure
    """
    # Validate track
    track = db.execute(select(Track).where(Track.id == track_id)).scalars().first()
    if not track:
        return None, "Track not found"
    if not track.audio_url:
        return None, "Track has no available audio_url for streaming"

    # Persist a start event; duration 0 for start marker
    start_event = PlaybackHistory(
        user_id=user_id,
        track_id=track_id,
        played_at=_now_utc(),
        duration_seconds=0,
    )
    try:
        db.add(start_event)
        db.commit()
    except Exception as e:
        db.rollback()
        return None, f"Failed to persist playback start: {e}"

    session = StreamSession(
        user_id=user_id,
        track_id=track_id,
        stream_url=track.audio_url,
        started_at=start_event.played_at,
    )
    return session, None


# PUBLIC_INTERFACE
def stop_streaming_session(
    db: Session,
    user_id: int,
    track_id: int,
    played_seconds: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Stop a streaming session for a given user and track.

    Behavior:
    - Records a PlaybackHistory row indicating the stop event with provided played_seconds.
    - If played_seconds is not provided or invalid, defaults to 0.

    Returns:
    - (True, None) on success
    - (False, "error message") on failure
    """
    # Keep it simple: just record another history event with the played duration reported by client
    duration = 0
    if isinstance(played_seconds, int) and played_seconds >= 0:
        duration = played_seconds

    stop_event = PlaybackHistory(
        user_id=user_id,
        track_id=track_id,
        played_at=_now_utc(),
        duration_seconds=duration,
    )
    try:
        db.add(stop_event)
        db.commit()
        return True, None
    except Exception as e:
        db.rollback()
        return False, f"Failed to persist playback stop: {e}"
