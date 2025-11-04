"""
Recommendations service for BackendAPI.

This module computes personalized track recommendations by combining:
- User's recent playback history (seed preference for artists/genres)
- Overall popular tracks (fallback/boosters)

It caches per-user results in the RecommendationsCache table to reduce
recomputation overhead. Cache invalidation strategy can be improved later
(e.g., time-based or event-based). For now, we refresh if cache is missing
or if the caller explicitly asks to refresh.

Design notes:
- Avoid heavy joins; use simple aggregate queries with SQL functions.
- Graceful behavior: if a user has no history, return popular tracks.
- Limit and deduplicate track IDs. Never recommend non-existent tracks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from sqlalchemy import func, select, desc
from sqlalchemy.orm import Session

from src.db.models import (
    PlaybackHistory,
    RecommendationsCache,
    Track,
)

DEFAULT_RECO_LIMIT = 25
CACHE_TTL_MINUTES = 60  # simple TTL; can be tuned or made configurable


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_cache_fresh(generated_at: datetime) -> bool:
    """Return True if cache is within TTL."""
    return (_now_utc() - generated_at) <= timedelta(minutes=CACHE_TTL_MINUTES)


def _fetch_recent_user_preferences(db: Session, user_id: int, recent_days: int = 30, max_seeds: int = 5) -> Tuple[List[int], List[str]]:
    """
    Analyze recent playback history to derive preference seeds.

    Returns:
    - top_artist_ids: top artist IDs the user listened to recently
    - top_genres: top genres the user listened to recently
    """
    since = _now_utc() - timedelta(days=recent_days)

    # Top artists
    artist_stmt = (
        select(Track.artist_id, func.count(PlaybackHistory.id).label("plays"))
        .join(Track, Track.id == PlaybackHistory.track_id)
        .where(PlaybackHistory.user_id == user_id, PlaybackHistory.played_at >= since)
        .group_by(Track.artist_id)
        .order_by(desc("plays"))
        .limit(max_seeds)
    )
    top_artist_ids = [row[0] for row in db.execute(artist_stmt).all() if row[0] is not None]

    # Top genres
    genre_stmt = (
        select(Track.genre, func.count(PlaybackHistory.id).label("plays"))
        .join(Track, Track.id == PlaybackHistory.track_id)
        .where(PlaybackHistory.user_id == user_id, PlaybackHistory.played_at >= since, Track.genre.is_not(None))
        .group_by(Track.genre)
        .order_by(desc("plays"))
        .limit(max_seeds)
    )
    top_genres = [row[0] for row in db.execute(genre_stmt).all() if row[0]]

    return top_artist_ids, top_genres


def _fetch_popular_tracks(db: Session, limit: int = DEFAULT_RECO_LIMIT) -> List[int]:
    """
    Fetch globally popular tracks, based on total playback counts.
    """
    stmt = (
        select(PlaybackHistory.track_id, func.count(PlaybackHistory.id).label("plays"))
        .group_by(PlaybackHistory.track_id)
        .order_by(desc("plays"))
        .limit(limit * 2)  # oversample to allow dedupe later
    )
    return [row[0] for row in db.execute(stmt).all() if row[0] is not None]


def _fetch_seeded_tracks(db: Session, artist_ids: List[int], genres: List[str], limit: int = DEFAULT_RECO_LIMIT) -> List[int]:
    """
    Fetch tracks that match user seed preferences. Prefer matches by artist or by genre.
    """
    track_ids: List[int] = []
    if artist_ids:
        stmt_artists = (
            select(Track.id)
            .where(Track.artist_id.in_(artist_ids))
            .order_by(desc(Track.created_at))
            .limit(limit)
        )
        track_ids.extend([row[0] for row in db.execute(stmt_artists).all()])

    if genres:
        stmt_genres = (
            select(Track.id)
            .where(func.lower(Track.genre).in_([g.lower() for g in genres]))
            .order_by(desc(Track.created_at))
            .limit(limit)
        )
        track_ids.extend([row[0] for row in db.execute(stmt_genres).all()])

    # Deduplicate while preserving order
    seen = set()
    deduped: List[int] = []
    for tid in track_ids:
        if tid not in seen:
            seen.add(tid)
            deduped.append(tid)

    return deduped[:limit]


def _filter_existing_tracks(db: Session, track_ids: List[int]) -> List[int]:
    """
    Ensure track IDs exist in DB (defensive).
    """
    if not track_ids:
        return []
    stmt = select(Track.id).where(Track.id.in_(track_ids))
    existing = [row[0] for row in db.execute(stmt).all()]
    existing_set = set(existing)
    return [tid for tid in track_ids if tid in existing_set]


# PUBLIC_INTERFACE
def compute_recommendations(db: Session, user_id: int, limit: int = DEFAULT_RECO_LIMIT, force_refresh: bool = False) -> List[Track]:
    """
    Compute or fetch cached personalized recommendations for a user.

    Strategy:
    - If cache exists and is fresh (unless force_refresh), return cached tracks.
    - Otherwise:
      - Derive seeds from recent playback (top artists and genres).
      - Fetch seeded tracks.
      - Blend with popular tracks as fallback.
      - Deduplicate and clip to limit.
      - Store in cache.

    Returns:
    - List[Track] ORM objects in a best-effort order of relevance.
    """
    # Try cache
    cache: RecommendationsCache | None = db.execute(
        select(RecommendationsCache).where(RecommendationsCache.user_id == user_id)
    ).scalars().first()

    if cache and not force_refresh and _is_cache_fresh(cache.generated_at):
        ids = list(cache.recommendations.get("track_ids", [])) if isinstance(cache.recommendations, dict) else []
        ids = _filter_existing_tracks(db, ids)[:limit]
        if not ids:
            # Cache empty or stale content; fall through to recompute
            pass
        else:
            # Load ORM in the given ID order
            if not ids:
                return []
            tracks_map = {t.id: t for t in db.execute(select(Track).where(Track.id.in_(ids))).scalars().all()}
            ordered = [tracks_map[tid] for tid in ids if tid in tracks_map]
            return ordered

    # Recompute
    top_artists, top_genres = _fetch_recent_user_preferences(db, user_id=user_id)

    seeded = _fetch_seeded_tracks(db, artist_ids=top_artists, genres=top_genres, limit=limit)

    popular = _fetch_popular_tracks(db, limit=limit)

    # Blend: seeded first, then fill with popular as needed
    combined: List[int] = []
    seen = set()

    for tid in seeded:
        if tid not in seen:
            seen.add(tid)
            combined.append(tid)
        if len(combined) >= limit:
            break

    if len(combined) < limit:
        for tid in popular:
            if tid not in seen:
                seen.add(tid)
                combined.append(tid)
            if len(combined) >= limit:
                break

    # If still underfilled (no history + no popular data), just pick recent tracks as last fallback
    if len(combined) < limit:
        recent_stmt = select(Track.id).order_by(desc(Track.created_at)).limit(limit)
        recent_ids = [row[0] for row in db.execute(recent_stmt).all()]
        for tid in recent_ids:
            if tid not in seen:
                seen.add(tid)
                combined.append(tid)
            if len(combined) >= limit:
                break

    combined = _filter_existing_tracks(db, combined)[:limit]

    # Update cache (upsert behavior)
    payload = {"track_ids": combined, "generated": _now_utc().isoformat()}
    if cache:
        cache.recommendations = payload
        cache.generated_at = _now_utc()
    else:
        cache = RecommendationsCache(user_id=user_id, recommendations=payload, generated_at=_now_utc())
        db.add(cache)
    db.commit()

    # Return ORM objects ordered
    if not combined:
        return []
    tracks_map = {t.id: t for t in db.execute(select(Track).where(Track.id.in_(combined))).scalars().all()}
    ordered = [tracks_map[tid] for tid in combined if tid in tracks_map]
    return ordered
