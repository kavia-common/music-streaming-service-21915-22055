# Database Layer

This directory contains:
- models.py: SQLAlchemy ORM models (users, artists, albums, tracks, playlists, playlist_tracks, playback_history, user_activity, admin_audit_logs, recommendations_cache)
- crud.py: data-access helpers for auth, playlists, catalog search
- session.py: engine and session factory, FastAPI dependency
- init_db.py: optional utility to create tables from metadata (use migrations in production)

Environment:
- DATABASE_URL must be provided via .env or environment variables (see src/core/config.py)
