"""
Pydantic schemas for streaming session APIs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StreamStartRequest(BaseModel):
    track_id: int = Field(..., description="Track ID to start streaming")


class StreamStartResponse(BaseModel):
    track_id: int = Field(..., description="Track ID that started streaming")
    stream_url: str = Field(..., description="Resolved audio URL to stream")
    started_at: datetime = Field(..., description="UTC timestamp when the stream started")


class StreamStopRequest(BaseModel):
    track_id: int = Field(..., description="Track ID to stop streaming")
    played_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of seconds actually played (best-effort, provided by client)",
    )
