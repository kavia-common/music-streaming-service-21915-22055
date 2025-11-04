"""
Database session management for SQLAlchemy 2.0 with PostgreSQL (psycopg).

This module exposes:
- engine: global SQLAlchemy engine
- SessionLocal: sessionmaker factory
- get_db: FastAPI dependency yielding a session per request
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import get_settings

settings = get_settings()

# Create SQLAlchemy engine for PostgreSQL using the configured DATABASE_URL.
# Pool settings tuned for typical web workloads; adjust as necessary.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


# PUBLIC_INTERFACE
def get_db() -> Generator:
    """FastAPI dependency that provides a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
