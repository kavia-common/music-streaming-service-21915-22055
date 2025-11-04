from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.api.routes.auth import router as auth_router
from src.api.routes.users import router as users_router
from src.api.routes.playlists import router as playlists_router
from src.api.routes.catalog import router as catalog_router
from src.api.routes.recommendations import router as recommendations_router
from src.api.routes.streaming import router as streaming_router
from src.api.routes.admin import router as admin_router
from src.middleware.observability import ObservabilityMiddleware

settings = get_settings()

openapi_tags = [
    {"name": "Health", "description": "Service health and readiness."},
    {"name": "Auth", "description": "User authentication and profile management."},
    {"name": "Playlists", "description": "Playlist management APIs."},
    {"name": "Catalog", "description": "Music catalog browsing and search."},
    {"name": "Streaming", "description": "Stream session orchestration (start/stop)."},
    {"name": "Admin", "description": "Administrative operations and audit."},
]

app = FastAPI(
    title="Music Streaming Backend API",
    description="RESTful API for music streaming platform backend services.",
    version="1.0.0",
    contact={"name": "Backend Team"},
    license_info={"name": "Proprietary"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conditionally add observability middleware
if settings.OBS_ENABLED:
    app.add_middleware(ObservabilityMiddleware)


@app.get(
    "/",
    summary="Health Check",
    tags=["Health"],
    responses={200: {"description": "Service is healthy"}},
)
def health_check():
    """Health check endpoint for liveness probes.

    Returns a simple JSON indicating the service is healthy.
    """
    return {"message": "Healthy"}


# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(playlists_router)
app.include_router(catalog_router)
app.include_router(recommendations_router)
app.include_router(streaming_router)
app.include_router(admin_router)
