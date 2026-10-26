"""Locations of the built frontend, plus the route that serves the SPA.

The SPA (app.html + assets/) is a normal multi-asset Vite build served from
/views/static/ and fetches its data from the REST API. Each MCP Apps view is
a single self-contained HTML file in dist/views/ (all JS and CSS inlined)
that gets its data from the show_* tool result via the ext-apps SDK, so it
is only served as a ui:// MCP resource — see mcp/server.py.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

# Vite build output lives in frontend/dist/ at the repo root (sibling of backend/)
DIST_DIR = Path(__file__).parents[3] / "frontend" / "dist"
VIEWS_DIR = DIST_DIR / "views"

router = APIRouter(tags=["views"])


def read_view_html(name: str) -> str:
    """Return a built single-file view's HTML as-is, or a placeholder if not built."""
    html_path = VIEWS_DIR / f"{name}.html"
    if not html_path.exists():
        return (
            f"<html><body><h1>View not found: {html_path.name}</h1>"
            f"<p>Run <code>npm run build</code> in frontend/.</p></body></html>"
        )
    return html_path.read_text()


@router.get("/views/app", response_class=HTMLResponse)
async def spa_view() -> HTMLResponse:
    """Serve the main SPA frontend (no data injection needed)."""
    html_path = DIST_DIR / "app.html"
    return HTMLResponse(content=html_path.read_text())
