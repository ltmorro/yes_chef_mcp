"""Unified ASGI entry point: FastAPI + FastMCP mount.

Both share the same process, SQLite connection pool, and port.
Claude Desktop connects via HTTP at /mcp, React UI hits REST at /api/*.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import Response

from yes_chef_mcp.api.routes import router
from yes_chef_mcp.api.views import DIST_DIR
from yes_chef_mcp.api.views import router as views_router
from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.mcp.server import mcp

logger = logging.getLogger(__name__)

mcp_app = mcp.http_app(path="/")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize database on startup, close on shutdown."""
    logger.info("yes_chef_mcp starting — initializing database")
    async with get_db():
        pass

    if hasattr(mcp_app, "lifespan") and mcp_app.lifespan:
        async with mcp_app.lifespan(app):
            yield
    else:
        yield

    logger.info("yes_chef_mcp shutting down")


app = FastAPI(
    title="yes_chef_mcp",
    description="Meal planning with macro optimization",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# REST API routes
app.include_router(router, prefix="/api")

# HTML view components (served at /api/views/*)
app.include_router(views_router, prefix="/api")


# Vite build output — served via a regular route so CORS middleware applies.
# (StaticFiles mounted via app.mount() bypasses middleware in Starlette 0.40+)
@app.get("/views/static/{path:path}", include_in_schema=False)
async def serve_static(path: str) -> Response:
    file_path = DIST_DIR / path
    if not file_path.exists() or not file_path.is_file():
        return Response(status_code=404)
    return FileResponse(file_path)


# Mount FastMCP's HTTP transport at /mcp
app.mount("/mcp", mcp_app)
