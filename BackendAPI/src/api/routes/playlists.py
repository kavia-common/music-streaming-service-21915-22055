"""
Playlists routes: manage user playlists and tracks within playlists.

Exposes:
- GET /playlists: List playlists for current user
- POST /playlists: Create a new playlist
- GET /playlists/{playlist_id}: Get playlist details (owned by current user)
- PATCH /playlists/{playlist_id}: Update playlist (owned by current user)
- DELETE /playlists/{playlist_id}: Delete playlist (owned by current user)
- POST /playlists/{playlist_id}/tracks: Add a track to a playlist
- DELETE /playlists/{playlist_id}/tracks/{track_id}: Remove a track from a playlist
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.db.crud import (
    add_track_to_playlist,
    delete_playlist,
    get_playlist,
    list_playlist_tracks,
    list_user_playlists,
    remove_track_from_playlist,
    update_playlist as crud_update_playlist,
    create_playlist as crud_create_playlist,
)
from src.db.models import User as UserModel, PlaylistTrack as PlaylistTrackModel
from src.schemas.playlists import (
    PlaylistCreate,
    PlaylistOut,
    PlaylistUpdate,
    PlaylistTrackItem,
)

router = APIRouter(prefix="/playlists", tags=["Playlists"])


def _serialize_playlist_with_tracks(playlist, tracks: Optional[List[PlaylistTrackModel]] = None) -> PlaylistOut:
    """
    Internal helper to map ORM Playlist (+ optional PlaylistTrack list) to PlaylistOut.
    """
    pt_items: List[PlaylistTrackItem] = []
    if tracks is None:
        tracks = list_playlist_tracks  # not used; always pass tracks when needed
        pt_items = []
    else:
        pt_items = [
            PlaylistTrackItem(track_id=pt.track_id, position=pt.position)
            for pt in tracks
        ]

    # Build PlaylistOut manually to include tracks list
    return PlaylistOut(
        id=playlist.id,
        owner_user_id=playlist.owner_user_id,
        name=playlist.name,
        description=playlist.description,
        cover_image=playlist.cover_image,
        is_public=playlist.is_public,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        tracks=pt_items,
    )


@router.get(
    "",
    summary="List user playlists",
    response_model=List[PlaylistOut],
    responses={
        200: {"description": "List of playlists"},
        401: {"description": "Unauthorized"},
    },
)
def list_playlists(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> List[PlaylistOut]:
    """
    Return all playlists belonging to the current authenticated user.
    """
    playlists = list_user_playlists(db, current_user.id)
    # For list view, do not load tracks to keep response light; return empty tracks.
    return [
        PlaylistOut(
            id=p.id,
            owner_user_id=p.owner_user_id,
            name=p.name,
            description=p.description,
            cover_image=p.cover_image,
            is_public=p.is_public,
            created_at=p.created_at,
            updated_at=p.updated_at,
            tracks=[],
        )
        for p in playlists
    ]


@router.post(
    "",
    summary="Create a new playlist",
    response_model=PlaylistOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Playlist created"},
        400: {"description": "Validation error"},
        401: {"description": "Unauthorized"},
    },
)
def create_playlist(
    payload: PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> PlaylistOut:
    """
    Create a playlist owned by the current user.

    Parameters:
    - name: playlist name (required)
    - description, cover_image, is_public: optional
    """
    playlist, err = crud_create_playlist(
        db,
        owner_user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        cover_image=payload.cover_image,
        is_public=payload.is_public or False,
    )
    if err or not playlist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Unable to create playlist")

    return PlaylistOut(
        id=playlist.id,
        owner_user_id=playlist.owner_user_id,
        name=playlist.name,
        description=playlist.description,
        cover_image=playlist.cover_image,
        is_public=playlist.is_public,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        tracks=[],
    )


@router.get(
    "/{playlist_id}",
    summary="Get playlist details",
    response_model=PlaylistOut,
    responses={
        200: {"description": "Playlist details"},
        401: {"description": "Unauthorized"},
        404: {"description": "Not found"},
    },
)
def get_playlist_details(
    playlist_id: int = Path(..., description="Playlist id"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> PlaylistOut:
    """
    Return details of a playlist owned by the current user, including the list of tracks.
    """
    playlist = get_playlist(db, playlist_id=playlist_id, owner_user_id=current_user.id)
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    tracks = list_playlist_tracks(db, playlist_id)
    return _serialize_playlist_with_tracks(playlist, tracks)


@router.patch(
    "/{playlist_id}",
    summary="Edit playlist",
    response_model=PlaylistOut,
    responses={
        200: {"description": "Playlist updated"},
        400: {"description": "Validation error"},
        401: {"description": "Unauthorized"},
        404: {"description": "Not found"},
    },
)
def update_playlist(
    playlist_id: int = Path(..., description="Playlist id"),
    updates: PlaylistUpdate = ...,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> PlaylistOut:
    """
    Update editable fields on a playlist owned by the current user.
    """
    updated = crud_update_playlist(
        db,
        playlist_id=playlist_id,
        owner_user_id=current_user.id,
        name=updates.name,
        description=updates.description,
        cover_image=updates.cover_image,
        is_public=updates.is_public,
    )
    if not updated:
        # Determine if not found vs no changes: if not found for user, get by id may reveal existence
        exists = get_playlist(db, playlist_id=playlist_id, owner_user_id=current_user.id)
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes applied")

    # Include tracks in response
    tracks = list_playlist_tracks(db, playlist_id)
    return _serialize_playlist_with_tracks(updated, tracks)


@router.delete(
    "/{playlist_id}",
    summary="Delete playlist",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Deleted"},
        401: {"description": "Unauthorized"},
        404: {"description": "Not found"},
    },
)
def delete_playlist_route(
    playlist_id: int = Path(..., description="Playlist id"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> None:
    """
    Delete a playlist owned by the current user. Returns 204 on success.
    """
    ok = delete_playlist(db, playlist_id=playlist_id, owner_user_id=current_user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")


@router.post(
    "/{playlist_id}/tracks",
    summary="Add track to playlist",
    response_model=PlaylistOut,
    responses={
        200: {"description": "Track added"},
        400: {"description": "Validation error"},
        401: {"description": "Unauthorized"},
        404: {"description": "Not found"},
    },
)
def add_track(
    playlist_id: int = Path(..., description="Playlist id"),
    track_id: int = Query(..., description="Track ID to add"),
    position: Optional[int] = Query(None, ge=0, description="Optional position to insert; append if omitted"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> PlaylistOut:
    """
    Add a track to a playlist owned by the current user.
    """
    playlist = get_playlist(db, playlist_id=playlist_id, owner_user_id=current_user.id)
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    link, err = add_track_to_playlist(db, playlist_id=playlist_id, track_id=track_id, position=position)
    if err or not link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Unable to add track")

    tracks = list_playlist_tracks(db, playlist_id)
    return _serialize_playlist_with_tracks(playlist, tracks)


@router.delete(
    "/{playlist_id}/tracks/{track_id}",
    summary="Remove track from playlist",
    response_model=PlaylistOut,
    responses={
        200: {"description": "Track removed"},
        401: {"description": "Unauthorized"},
        404: {"description": "Not found"},
    },
)
def remove_track(
    playlist_id: int = Path(..., description="Playlist id"),
    track_id: int = Path(..., description="Track id to remove"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> PlaylistOut:
    """
    Remove a track from a playlist owned by the current user.
    """
    playlist = get_playlist(db, playlist_id=playlist_id, owner_user_id=current_user.id)
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    ok = remove_track_from_playlist(db, playlist_id=playlist_id, track_id=track_id)
    if not ok:
        # When a specific track isn't in the playlist, treat as 404 as the frontend expects feedback.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found in playlist")

    tracks = list_playlist_tracks(db, playlist_id)
    return _serialize_playlist_with_tracks(playlist, tracks)
