"""Unified ASGI entry point: FastAPI + FastMCP mount.

Both share the same process, SQLite connection pool, and port.
Claude Desktop connects via SSE at /mcp/sse, React UI hits REST at /api/*.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mealmcp.api.routes import router
from mealmcp.api.views import router as views_router
from mealmcp.core.db import get_db
from mealmcp.mcp.server import mcp
from mealmcp.views import VIEWS_DIR

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize database on startup, close on shutdown."""
    logger.info("MealMCP starting — initializing database")
    async with get_db():
        pass
    yield
    logger.info("MealMCP shutting down")


app = FastAPI(
    title="MealMCP",
    description="Meal planning with macro optimization",
    version="0.1.0",
    lifespan=lifespan,
)

# REST API routes
app.include_router(router, prefix="/api")

# HTML view components (served at /api/views/*)
app.include_router(views_router, prefix="/api")

# Static assets for view components (shared.js, etc.)
app.mount("/views/static", StaticFiles(directory=str(VIEWS_DIR)), name="view-static")

# Mount FastMCP's SSE transport at /mcp
app.mount("/mcp", mcp.sse_app())
