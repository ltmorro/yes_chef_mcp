"""Unified ASGI entry point: FastAPI + FastMCP mount.

Both share the same process, SQLite connection pool, and port.
Claude Desktop connects via HTTP at /mcp, React UI hits REST at /api/*.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from yes_chef_mcp.api.routes import router
from yes_chef_mcp.api.views import DIST_DIR, router as views_router
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

# REST API routes
app.include_router(router, prefix="/api")

# HTML view components (served at /api/views/*)
app.include_router(views_router, prefix="/api")

# Vite build output — JS/CSS bundles referenced by the HTML views
app.mount("/views/static", StaticFiles(directory=str(DIST_DIR)), name="view-static")

# Mount FastMCP's HTTP transport at /mcp
app.mount("/mcp", mcp_app)
