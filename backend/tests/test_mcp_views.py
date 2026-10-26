"""Tests for the MCP Apps view tools and their ui:// resources."""

from __future__ import annotations

import re
import sys
from datetime import date

import pytest
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError
from mcp.types import TextResourceContents
from pydantic import BaseModel

from yes_chef_mcp.api.views import VIEWS_DIR
from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.models import MealType, Recipe
from yes_chef_mcp.core.planner import add_meal_slot, create_meal_plan
from yes_chef_mcp.core.schemas import (
    GroceryListDataSchema,
    MacroSetterDataSchema,
    RecipeSelectorDataSchema,
    WeeklyCalendarDataSchema,
)
from yes_chef_mcp.mcp.server import mcp

VIEW_TOOLS: dict[str, str] = {
    "show_macro_target_setter": "ui://yes_chef_mcp/macro-setter.html",
    "show_recipe_selector": "ui://yes_chef_mcp/recipe-selector.html",
    "show_weekly_calendar": "ui://yes_chef_mcp/weekly-calendar.html",
    "show_grocery_checklist": "ui://yes_chef_mcp/grocery-list.html",
}

MCP_APP_MIME = "text/html;profile=mcp-app"


@pytest.fixture(autouse=True)
def _no_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force FTS-only search: importing the embeddings module raises ImportError.

    Otherwise show_recipe_selector would try to download a sentence-transformers
    model over the network.
    """
    monkeypatch.setitem(sys.modules, "yes_chef_mcp.pipeline.embeddings", None)


@pytest.fixture()
async def sample_member_id(sample_family_id: str) -> str:
    member_id = "member-test-1"
    async with get_db() as db:
        await db.execute(
            "INSERT INTO members (id, family_id, name, role, is_default) VALUES (?, ?, ?, ?, ?)",
            (member_id, sample_family_id, "Tester", "member", 1),
        )
    return member_id


@pytest.fixture()
async def sample_plan_id(sample_family_id: str, sample_recipes: list[Recipe]) -> str:
    plan = await create_meal_plan(sample_family_id, "Test Week", date(2026, 4, 1))
    await add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-chicken")
    await add_meal_slot(plan.id, 0, MealType.DINNER, "recipe-quinoa")
    return plan.id


# ── Wiring ────────────────────────────────────────────────────────────────


async def test_view_tools_link_ui_resources() -> None:
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}

    for tool_name, uri in VIEW_TOOLS.items():
        meta = tools[tool_name].meta or {}
        assert meta["ui"]["resourceUri"] == uri
        assert tools[tool_name].outputSchema is not None


async def test_view_resources_are_mcp_apps() -> None:
    async with Client(mcp) as client:
        for uri in VIEW_TOOLS.values():
            contents = await client.read_resource(uri)
            assert contents[0].mimeType == MCP_APP_MIME


@pytest.mark.skipif(
    not VIEWS_DIR.is_dir(), reason="frontend not built (run `npm run build` in frontend/)"
)
async def test_view_resources_are_self_contained() -> None:
    async with Client(mcp) as client:
        for uri in VIEW_TOOLS.values():
            contents = await client.read_resource(uri)
            item = contents[0]
            assert isinstance(item, TextResourceContents)
            html = item.text

            assert "localhost" not in html
            assert "unpkg" not in html
            assert not re.search(r"<script[^>]*\bsrc=", html), f"{uri} loads an external script"
            assert re.search(r"<script[^>]*>\s*\S", html), f"{uri} has no inlined script"


# ── Payloads ──────────────────────────────────────────────────────────────


async def _call_view(
    client: Client[FastMCPTransport], tool_name: str, args: dict[str, str], schema: type[BaseModel]
) -> tuple[str, BaseModel]:
    result = await client.call_tool(tool_name, args)
    assert result.structured_content is not None
    assert "result" not in result.structured_content  # not a json.dumps string wrapper
    payload = schema.model_validate(result.structured_content)
    text = result.content[0]
    assert text.type == "text"
    return text.text, payload


async def test_show_macro_target_setter_payload(sample_member_id: str) -> None:
    async with Client(mcp) as client:
        await client.call_tool(
            "set_macro_target",
            {
                "member_id": sample_member_id,
                "name": "Cut",
                "calories": 2000,
                "protein_g": 150,
                "carbs_g": 200,
                "fat_g": 60,
            },
        )
        summary, payload = await _call_view(
            client,
            "show_macro_target_setter",
            {"member_id": sample_member_id},
            MacroSetterDataSchema,
        )

    assert isinstance(payload, MacroSetterDataSchema)
    assert payload.current_targets is not None
    assert payload.current_targets.name == "Cut"
    assert payload.current_targets.protein_g == 150
    assert "Cut" in summary


async def test_show_macro_target_setter_without_targets(sample_member_id: str) -> None:
    async with Client(mcp) as client:
        _, payload = await _call_view(
            client,
            "show_macro_target_setter",
            {"member_id": sample_member_id},
            MacroSetterDataSchema,
        )

    assert isinstance(payload, MacroSetterDataSchema)
    assert payload.current_targets is None
    assert payload.member_id == sample_member_id
    assert payload.target_name == "Custom"


async def test_show_macro_target_setter_uses_default_member(sample_member_id: str) -> None:
    async with Client(mcp) as client:
        summary, payload = await _call_view(
            client, "show_macro_target_setter", {}, MacroSetterDataSchema
        )

    assert isinstance(payload, MacroSetterDataSchema)
    assert payload.member_id == sample_member_id
    assert payload.member_name == "Tester"
    assert "Tester" in summary


async def test_show_macro_target_setter_without_default_member_raises(
    sample_family_id: str,
) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO members (id, family_id, name, role, is_default) VALUES (?, ?, ?, ?, ?)",
            ("member-not-default", sample_family_id, "Sam", "member", 0),
        )
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="pass a member_id"):
            await client.call_tool("show_macro_target_setter", {})


async def test_show_macro_target_setter_unknown_member_raises() -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="Member not found: 'nobody'"):
            await client.call_tool("show_macro_target_setter", {"member_id": "nobody"})


async def test_macro_setter_save_tool_is_listed_for_views() -> None:
    """The macro setter saves via set_macro_target, so it must stay in tools/list
    under its plain name without an app-excluding visibility."""
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}

    assert "set_macro_target" in tools
    visibility = ((tools["set_macro_target"].meta or {}).get("ui") or {}).get("visibility")
    assert visibility is None or "app" in visibility


async def test_show_recipe_selector_payload(sample_recipes: list[Recipe]) -> None:
    async with Client(mcp) as client:
        summary, payload = await _call_view(
            client, "show_recipe_selector", {"query": "chicken"}, RecipeSelectorDataSchema
        )

    assert isinstance(payload, RecipeSelectorDataSchema)
    assert "recipe-chicken" in [r.id for r in payload.recipes]
    chicken = next(r for r in payload.recipes if r.id == "recipe-chicken")
    assert chicken.macro_summary.protein_g == 45.0
    assert summary.startswith("Showing ")
    assert "for 'chicken'" in summary


async def test_show_weekly_calendar_payload(sample_plan_id: str, sample_member_id: str) -> None:
    async with Client(mcp) as client:
        await client.call_tool(
            "set_macro_target",
            {
                "member_id": sample_member_id,
                "name": "Maintain",
                "calories": 2200,
                "protein_g": 140,
                "carbs_g": 250,
                "fat_g": 70,
            },
        )
        summary, payload = await _call_view(
            client,
            "show_weekly_calendar",
            {"plan_id": sample_plan_id, "member_id": sample_member_id},
            WeeklyCalendarDataSchema,
        )

    assert isinstance(payload, WeeklyCalendarDataSchema)
    assert payload.plan_id == sample_plan_id
    assert payload.member_id == sample_member_id
    assert payload.plan_summary.plan_id == sample_plan_id
    assert payload.plan_summary.plan_name == "Test Week"
    assert payload.targets is not None
    assert payload.targets.calories == 2200
    assert {r.id for r in payload.recipes} == {"recipe-chicken", "recipe-quinoa"}
    assert "Test Week" in summary


async def test_show_grocery_checklist_payload(sample_plan_id: str) -> None:
    async with Client(mcp) as client:
        summary, payload = await _call_view(
            client, "show_grocery_checklist", {"plan_id": sample_plan_id}, GroceryListDataSchema
        )

    assert isinstance(payload, GroceryListDataSchema)
    assert payload.grocery_list.plan_id == sample_plan_id
    names = {item.name.lower() for item in payload.grocery_list.items}
    assert "chicken breast" in names
    assert f"{len(payload.grocery_list.items)} items" in summary


async def test_show_weekly_calendar_without_member(sample_plan_id: str) -> None:
    async with Client(mcp) as client:
        _, payload = await _call_view(
            client, "show_weekly_calendar", {"plan_id": sample_plan_id}, WeeklyCalendarDataSchema
        )

    assert isinstance(payload, WeeklyCalendarDataSchema)
    assert payload.plan_id == sample_plan_id
    assert payload.member_id is None
    assert payload.targets is None
