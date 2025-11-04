"""
Utility to create all tables from SQLAlchemy metadata.

Note: In production use proper migration tooling (e.g., Alembic).
"""

from src.db.models import Base
from src.db.session import engine


# PUBLIC_INTERFACE
def create_all_tables() -> None:
    """Create all tables if they do not exist yet."""
    # Simple heuristic: create all unconditionally (SQLAlchemy will no-op existing)
    Base.metadata.create_all(bind=engine)
