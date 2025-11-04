"""
Catalog routes: search artists, albums, and tracks with optional filters.

Exposes:
- GET /catalog/search: Search the catalog by query with optional filters and pagination
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.db.crud import search_catalog
from src.schemas.catalog import AlbumOut, ArtistOut, TrackOut

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get(
    "/search",
    summary="Search music catalog",
    responses={
        200: {"description": "Search results"},
    },
)
def catalog_search(
    query: str = Query(..., description="Search query term"),
    genre: Optional[str] = Query(None, description="Optional genre filter"),
    artist: Optional[str] = Query(None, description="Optional artist filter (name)"),
    album: Optional[str] = Query(None, description="Optional album filter (title)"),
    limit: int = Query(25, ge=1, le=100, description="Max items per entity to return"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    db: Session = Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search the catalog across artists, albums, and tracks.

    Parameters:
    - query: free-text search term (required)
    - genre: optional genre filter (applies to tracks)
    - artist: optional artist name filter (exact match)
    - album: optional album title filter (exact match)
    - limit: maximum items to return per category (artists, albums, tracks)
    - page: page number for pagination (1-indexed)

    Returns:
    - JSON object with keys 'artists', 'albums', 'tracks', each a list of DTOs.
    """
    offset = (page - 1) * limit

    raw_results = search_catalog(
        db=db,
        query=query,
        genre=genre,
        artist=artist,
        album=album,
        limit=limit,
        offset=offset,
    )

    # Normalize ORM objects into Pydantic DTOs using existing schemas
    artists_out = [ArtistOut.model_validate(a).model_dump() for a in raw_results.get("artists", [])]
    albums_out = [AlbumOut.model_validate(al).model_dump() for al in raw_results.get("albums", [])]
    tracks_out = [TrackOut.model_validate(t).model_dump() for t in raw_results.get("tracks", [])]

    return {
        "artists": artists_out,
        "albums": albums_out,
        "tracks": tracks_out,
    }
