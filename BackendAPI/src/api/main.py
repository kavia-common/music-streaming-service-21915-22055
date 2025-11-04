from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Music Streaming Backend API",
    description="RESTful API for music streaming platform backend services.",
    version="1.0.0",
    contact={"name": "Backend Team"},
    license_info={"name": "Proprietary"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
