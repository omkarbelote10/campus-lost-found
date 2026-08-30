from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
from pathlib import Path

# Without this the root logger sits at WARNING and every application INFO line is
# dropped -- including which device SigLIP loaded onto. Only errors were visible.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s: %(message)s",
)

from app.core.config import get_settings
from app.core.database import Base, engine

# Import routers
from app.api import auth, items, matches, claims, admin

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Campus Lost-and-Found Intelligence System",
    description="Enterprise AIML platform for automated item retrieval",
    version="1.0.0"
)

settings = get_settings()


def _warm_embedding_models() -> None:
    """Load the embedding weights ahead of the first request.

    The towers load lazily on first use, which keeps startup instant but hands
    the cost to whoever files the first report -- measured at ~8s (SigLIP 6.7s,
    DINOv2 1.2s). That reads as "matching is slow" when it is really "matching is
    slow once".

    Deliberately on a daemon thread: startup must not block on this, so the
    health check passes and every non-matching route serves immediately while the
    weights stream in. A daemon thread also will not hold the process open at
    shutdown if a load is still in flight.
    """
    import threading
    import time

    if not settings.EMBEDDINGS_ENABLED or not settings.WARM_EMBEDDINGS_ON_STARTUP:
        return

    def warm() -> None:
        from app.services.embeddings import get_embedder

        logger = logging.getLogger(__name__)
        started = time.perf_counter()
        embedder = get_embedder()
        # _ensure_loaded latches and logs its own failures, so a model that
        # cannot load leaves the app running with matching degraded rather than
        # taking startup down with it.
        embedder.text._ensure_loaded()
        embedder.image._ensure_loaded()
        logger.info(
            "embedding models warm after %.1fs; the first report will not pay the load",
            time.perf_counter() - started,
        )

    threading.Thread(target=warm, name="warm-embeddings", daemon=True).start()


_warm_embedding_models()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploads
upload_path = Path(settings.UPLOAD_DIR)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(items.router, prefix="/api/items", tags=["Items"])
app.include_router(matches.router, prefix="/api/matches", tags=["Matches"])
app.include_router(claims.router, prefix="/api/claims", tags=["Claims"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

@app.get("/")
async def root():
    return {
        "message": "Campus Lost-and-Found Intelligence System",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Liveness plus which device the embedder resolved to.

    Reports the resolved device without forcing a load, so hitting this endpoint
    never triggers the model download. `model_loaded` stays false until the first
    report actually needs an embedding.
    """
    from app.services.embeddings import get_embedder, resolve_device

    embedder = get_embedder()
    device = resolve_device()
    return {
        "status": "healthy",
        "embeddings": {
            "enabled": settings.EMBEDDINGS_ENABLED,
            "device": device,
            "text": {
                "model": embedder.text.model_name,
                "loaded": embedder.text.is_available,
            },
            "image": {
                "model": embedder.image.model_name,
                "loaded": embedder.image.is_available,
            },
        },
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
