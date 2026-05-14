"""FastAPI application factory."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import CORS_ORIGINS
from .schemas import HealthResponse

_log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    _log.info("Creating FastAPI app")
    app = FastAPI(title="Alarm Viewer API", version="0.1.0")

    @app.middleware("http")
    async def limit_mcp_tunnel_access(request, call_next):
        tunnel_host = os.environ.get("ALARM_MCP_TUNNEL_HOST_HEADER", "alarm-viewer-mcp.local").lower()
        request_host = request.headers.get("host", "").split(":", 1)[0].lower()
        if request_host == tunnel_host and request.url.path != "/mcp":
            return JSONResponse(
                {"detail": "Tunnel access is limited to the MCP endpoint"},
                status_code=403,
            )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routers import alarms, mcp, pm, sync
    app.include_router(sync.router)
    app.include_router(alarms.router)
    app.include_router(pm.router)
    app.include_router(mcp.router)

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(status="ok", version="0.1.0")

    return app
