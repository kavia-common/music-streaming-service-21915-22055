"""
Core configuration for the BackendAPI service.

Loads all required environment variables and provides typed access to them.
Uses Pydantic BaseSettings to support .env loading and environment overrides.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Note: Values can be provided in a .env file or process env vars.
    """

    # Server
    API_HOST: str = Field(default="0.0.0.0", description="Host interface for FastAPI server")
    API_PORT: int = Field(default=8000, description="Port for FastAPI server")

    # CORS
    CORS_ORIGINS: List[AnyHttpUrl] | List[str] = Field(
        default=["*"],
        description="Allowed CORS origins. Provide as a JSON array or comma-separated string.",
    )

    # Database (PostgreSQL SQLAlchemy URL)
    # Example: postgresql+psycopg://user:password@host:5432/dbname
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/music",
        description="SQLAlchemy database URL for PostgreSQL using psycopg driver",
    )

    # JWT / Auth
    JWT_SECRET: str = Field(default="change-me", description="JWT secret used to sign tokens")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="Access token TTL in minutes")

    # Observability / Logging related environment variables
    OBS_ENABLED: bool = Field(default=True, description="Enable observability/log forwarding")
    # Support both OBS_BASE_URL (preferred) and OBS_ENDPOINT (legacy)
    OBS_BASE_URL: Optional[str] = Field(default=None, description="Observability service base URL (e.g., http://monitoring:8000)")
    OBS_ENDPOINT: Optional[str] = Field(default=None, description="Legacy env var for observability endpoint (fallback to OBS_BASE_URL)")
    OBS_API_KEY: Optional[str] = Field(default=None, description="Observability service API key")
    OBS_SERVICE_NAME: str = Field(default="backend-api", description="Service name for tracing/logs")
    OBS_ENVIRONMENT: str = Field(default="development", description="Deployment environment")

    class Config:
        env_file = ".env"
        extra = "ignore"

    @classmethod
    def parse_cors_origins(cls, value: List[str] | str) -> List[str]:
        """Normalize CORS origins from env (list or comma-separated string) to a list of strings."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Allow JSON-like list or comma-separated
            v = value.strip()
            if v.startswith("[") and v.endswith("]"):
                # Remove brackets and split by comma
                v = v[1:-1]
            return [item.strip().strip('"').strip("'") for item in v.split(",") if item.strip()]
        return ["*"]


# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the singleton Settings instance, with CORS origins normalized and observability normalized."""
    settings = Settings()  # type: ignore[call-arg]
    # Normalize CORS origins into list[str]
    settings.CORS_ORIGINS = Settings.parse_cors_origins(settings.CORS_ORIGINS)  # type: ignore[assignment]

    # Normalize observability base URL: prefer OBS_BASE_URL if provided
    try:
        if getattr(settings, "OBS_BASE_URL", None) and not getattr(settings, "OBS_ENDPOINT", None):
            settings.OBS_ENDPOINT = settings.OBS_BASE_URL  # type: ignore[attr-defined]
    except Exception:
        # Do not fail on any error
        pass

    return settings
