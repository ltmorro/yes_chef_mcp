"""FastAPI routes for serving HTML view components.

Each view is a self-contained React app that can be served standalone
or embedded in the MCP app layer. Data is injected via a JSON script
tag that the React code reads on mount.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from yes_chef_mcp.mcp.server import (
    generate_grocery_list,
    get_macro_targets,
    get_meal_plan_summary,
    search_recipes_by_query,
)

# Vite build output lives in frontend/dist/ at the repo root (sibling of backend/)
DIST_DIR = Path(__file__).parents[3] / "frontend" / "dist"

router = APIRouter(tags=["views"])


def _inject_data(html_path: Path, data: dict[str, object]) -> str:
    """Read an HTML file and inject JSON data into the <script id="view-data"> tag."""
    html = html_path.read_text()
    data_json = json.dumps(data, default=str)
    html = html.replace(
        '<script id="view-data" type="application/json">{}</script>',
        f'<script id="view-data" type="application/json">{data_json}</script>',
    )
    return html


@router.get("/views/macro-setter", response_class=HTMLResponse)
async def macro_setter_view(member_id: str | None = None) -> HTMLResponse:
    """Render the macro target setter with current targets pre-loaded."""
    targets = await get_macro_targets(member_id)
    active = next((t for t in targets if t.is_active), None)

    data: dict[str, object] = {}
    if active:
        data["current_targets"] = {
            "protein_g": active.protein_g,
            "carbs_g": active.carbs_g,
            "fat_g": active.fat_g,
            "calories": active.calories,
            "name": active.name,
        }

    html = _inject_data(DIST_DIR / "macro-setter.html", data)
    return HTMLResponse(content=html)


@router.get("/views/recipe-selector", response_class=HTMLResponse)
async def recipe_selector_view(
    q: str = "",
    category: str | None = None,
    tags: str | None = None,
    max_results: int = 20,
) -> HTMLResponse:
    """Render recipe selector with search results pre-loaded."""
    tag_list = tags.split(",") if tags else None

    result = await search_recipes_by_query(
        query=q,
        category=category,
        tags=tag_list,
        max_results=max_results,
    )

    recipes = [
        {
            "id": hit.id,
            "name": hit.name,
            "category": hit.category,
            "tags": hit.tags,
            "prep_minutes": hit.prep_minutes,
            "cook_minutes": hit.cook_minutes,
            "macro_summary": {
                "calories": hit.macro_summary.calories,
                "protein_g": hit.macro_summary.protein_g,
                "carbs_g": hit.macro_summary.carbs_g,
                "fat_g": hit.macro_summary.fat_g,
            },
        }
        for hit in result.hits
    ]

    html = _inject_data(DIST_DIR / "recipe-selector.html", {"recipes": recipes})
    return HTMLResponse(content=html)


@router.get("/views/weekly-calendar", response_class=HTMLResponse)
async def weekly_calendar_view(
    plan_id: str,
    member_id: str | None = None,
) -> HTMLResponse:
    """Render weekly calendar with full plan summary pre-loaded."""
    summary = await get_meal_plan_summary(plan_id, member_id, detail_level="full")

    targets: dict[str, object] | None = None
    if member_id:
        target_list = await get_macro_targets(member_id)
        active = next((t for t in target_list if t.is_active), None)
        if active:
            targets = {
                "calories": active.calories,
                "protein_g": active.protein_g,
                "carbs_g": active.carbs_g,
                "fat_g": active.fat_g,
            }

    data: dict[str, object] = {"plan_summary": summary.model_dump()}
    if targets:
        data["targets"] = targets

    html = _inject_data(DIST_DIR / "weekly-calendar.html", data)
    return HTMLResponse(content=html)


@router.get("/views/grocery-list", response_class=HTMLResponse)
async def grocery_list_view(
    plan_id: str,
    merge_similar: bool = True,
    exclude_pantry: bool = True,
) -> HTMLResponse:
    """Render grocery list checklist pre-loaded with items."""
    grocery = await generate_grocery_list(plan_id, merge_similar, exclude_pantry)

    data: dict[str, object] = {"grocery_list": grocery.model_dump()}
    html = _inject_data(DIST_DIR / "grocery-list.html", data)
    return HTMLResponse(content=html)


@router.get("/views/app", response_class=HTMLResponse)
async def spa_view() -> HTMLResponse:
    """Serve the main SPA frontend (no data injection needed)."""
    html_path = DIST_DIR / "app.html"
    return HTMLResponse(content=html_path.read_text())
