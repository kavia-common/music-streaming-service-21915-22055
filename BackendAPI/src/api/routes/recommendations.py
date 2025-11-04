"""
Recommendations routes: personalized music suggestions for the current user.

Exposes:
- GET /recommendations: Returns a list of recommended tracks (TrackOut[]) for the authenticated user.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.db.models import User as UserModel
from src.schemas.catalog import TrackOut
from src.services.recommendations import compute_recommendations

router = APIRouter(prefix="", tags=["Catalog"])


@router.get(
    "/recommendations",
    summary="Get personalized recommendations",
    response_model=List[TrackOut],
    responses={
        200: {"description": "Recommendations list"},
        401: {"description": "Unauthorized"},
    },
)
def get_recommendations(
    limit: int = Query(25, ge=1, le=100, description="Maximum number of tracks to return"),
    refresh: Optional[bool] = Query(False, description="Force refresh of cached recommendations"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> List[TrackOut]:
    """
    Return a list of personalized track recommendations for the current user.

    Parameters:
    - limit: maximum number of recommended tracks (default 25)
    - refresh: if true, bypass cache and recompute recommendations

    Behavior:
    - Combines recent playback preferences with popular tracks as fallback.
    - Gracefully handles cases with no history or insufficient seed data.

    Returns:
    - List of TrackOut DTOs ordered by estimated relevance.
    """
    tracks = compute_recommendations(db, user_id=current_user.id, limit=limit, force_refresh=bool(refresh))
    return [TrackOut.model_validate(t) for t in tracks]
