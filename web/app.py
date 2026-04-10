"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .schemas import HealthResponse


def create_app() -> FastAPI:
    app = FastAPI(title="Alarm Viewer API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routers import sync, alarms, pm
    app.include_router(sync.router)
    app.include_router(alarms.router)
    app.include_router(pm.router)

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(status="ok", version="0.1.0")

    return app


app = create_app()
