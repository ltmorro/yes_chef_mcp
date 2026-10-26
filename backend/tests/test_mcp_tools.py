"""Tests for the MCP data tools, exercised through an in-memory FastMCP client."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.members import list_macro_targets
from yes_chef_mcp.core.models import (
    DetailLevel,
    MealType,
    RebalanceStrategy,
    Recipe,
    RecipeCategory,
)
from yes_chef_mcp.mcp.server import mcp

WRITE_TOOLS = {"create_meal_plan", "add_to_meal_plan", "set_macro_target"}
READ_TOOLS = {
    "search_recipes_by_query",
    "search_recipes_by_macros",
    "get_recipe_detail",
    "compose_meal",
    "suggest_meal_complement",
    "get_meal_plan_summary",
    "generate_grocery_list",
    "list_tags",
    "list_categories",
    "get_macro_targets",
    "list_family_members",
    "optimize_meal",
    "optimize_plan",
    "rebalance_plan",
}
DATA_TOOLS = WRITE_TOOLS | READ_TOOLS

MEMBER_ID = "member-test-1"

type Json = dict[str, object]


@pytest.fixture()
async def client() -> AsyncIterator[Client]:
    async with Client(mcp) as c:
        yield c


@pytest.fixture()
async def sample_member_id(sample_family_id: str) -> str:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO members (id, family_id, name, role, is_default) VALUES (?, ?, ?, ?, ?)",
            (MEMBER_ID, sample_family_id, "Alex", "admin", 1),
        )
    return MEMBER_ID


@pytest.fixture(autouse=True)
def _no_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep search FTS-only so tests never load the sentence-transformers model."""

    def _unavailable(query: str) -> list[float]:
        raise ImportError("embeddings disabled in tests")

    monkeypatch.setattr("yes_chef_mcp.pipeline.embeddings.generate_query_embedding", _unavailable)


async def _call(client: Client, name: str, args: Json | None = None) -> Json:
    result = await client.call_tool(name, args or {})
    assert result.structured_content is not None
    return result.structured_content


async def _call_list(
    client: Client,
    name: str,
    args: Json | None = None,
) -> list[Json]:
    content = await _call(client, name, args)
    items = content["result"]
    assert isinstance(items, list)
    return items


# ── Metadata ─────────────────────────────────────────────────────────────


async def test_every_data_tool_has_title_and_annotations(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    assert tools.keys() >= DATA_TOOLS

    for name in DATA_TOOLS:
        tool = tools[name]
        assert tool.title, f"{name} has no title"
        assert tool.annotations is not None, f"{name} has no annotations"
        assert tool.annotations.readOnlyHint is (name in READ_TOOLS), name
        assert tool.annotations.openWorldHint is False, name
        if name in WRITE_TOOLS:
            assert tool.annotations.destructiveHint is not None, name
            assert tool.annotations.idempotentHint is not None, name


def _enum_values(prop: Json) -> list[str]:
    """Pull enum values out of a property schema, unwrapping Optional/list."""
    if "enum" in prop:
        values = prop["enum"]
        assert isinstance(values, list)
        return values
    if "items" in prop:
        items = prop["items"]
        assert isinstance(items, dict)
        return _enum_values(items)
    for option in prop.get("anyOf", []):
        if option.get("type") != "null":
            return _enum_values(option)
    raise AssertionError(f"no enum in {prop}")


@pytest.mark.parametrize(
    ("tool_name", "param", "enum_values"),
    [
        ("search_recipes_by_query", "category", [c.value for c in RecipeCategory]),
        ("search_recipes_by_macros", "category", [c.value for c in RecipeCategory]),
        ("suggest_meal_complement", "complement_category", [c.value for c in RecipeCategory]),
        ("add_to_meal_plan", "meal_type", [m.value for m in MealType]),
        ("optimize_meal", "meal_type", [m.value for m in MealType]),
        ("optimize_plan", "meal_types", [m.value for m in MealType]),
        ("rebalance_plan", "strategy", [s.value for s in RebalanceStrategy]),
        ("get_meal_plan_summary", "detail_level", [d.value for d in DetailLevel]),
    ],
)
async def test_enum_params_advertised_in_schema(
    client: Client,
    tool_name: str,
    param: str,
    enum_values: list[str],
) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    props = tools[tool_name].inputSchema["properties"]
    assert _enum_values(props[param]) == enum_values


async def test_compose_meal_components_are_typed(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    items = tools["compose_meal"].inputSchema["properties"]["components"]["items"]
    assert items["properties"].keys() == {"recipe_id", "servings"}
    assert items["required"] == ["recipe_id"]


async def test_invalid_enum_value_rejected(client: Client) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("get_meal_plan_summary", {"plan_id": "x", "detail_level": "hourly"})


# ── Happy paths ──────────────────────────────────────────────────────────


async def test_search_recipes_by_query(
    client: Client,
    sample_recipes: list[Recipe],
) -> None:
    page = await _call(client, "search_recipes_by_query", {"query": "chicken", "category": "main"})
    hits = page["hits"]
    assert isinstance(hits, list)
    assert [h["id"] for h in hits] == ["recipe-chicken"]


async def test_search_recipes_by_query_falls_back_when_model_download_fails(
    client: Client,
    sample_recipes: list[Recipe],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Offline with no cached model: HF raises OSError; search degrades to FTS-only."""

    def _offline(query: str) -> list[float]:
        raise OSError("We couldn't connect to 'https://huggingface.co' to load this file")

    monkeypatch.setattr("yes_chef_mcp.pipeline.embeddings.generate_query_embedding", _offline)

    page = await _call(client, "search_recipes_by_query", {"query": "chicken"})
    hits = page["hits"]
    assert isinstance(hits, list)
    assert [h["id"] for h in hits] == ["recipe-chicken"]
    assert "falling back to keyword search" in caplog.text


async def test_get_recipe_detail(
    client: Client,
    sample_recipes: list[Recipe],
) -> None:
    detail = await _call(client, "get_recipe_detail", {"recipe_id": "recipe-quinoa"})
    assert detail["name"] == "Quinoa Salad"
    nutrition = detail["nutrition"]
    assert isinstance(nutrition, dict)
    assert nutrition["calories"] == 220.0


async def test_compose_meal(
    client: Client,
    sample_recipes: list[Recipe],
) -> None:
    meal = await _call(
        client,
        "compose_meal",
        {
            "components": [
                {"recipe_id": "recipe-chicken", "servings": 2.0},
                {"recipe_id": "recipe-quinoa"},
            ]
        },
    )
    totals = meal["totals"]
    assert isinstance(totals, dict)
    assert totals["calories"] == pytest.approx(280.0 * 2 + 220.0)
    assert totals["protein_g"] == pytest.approx(45.0 * 2 + 8.0)


async def test_suggest_meal_complement(
    client: Client,
    sample_recipes: list[Recipe],
    sample_member_id: str,
) -> None:
    await _call(
        client,
        "set_macro_target",
        {
            "member_id": sample_member_id,
            "name": "Cut",
            "calories": 600,
            "protein_g": 55,
            "carbs_g": 40,
            "fat_g": 15,
        },
    )
    suggestions = await _call_list(
        client,
        "suggest_meal_complement",
        {
            "existing_components": [{"recipe_id": "recipe-chicken"}],
            "member_id": sample_member_id,
        },
    )
    assert all(s["category"] == "side" for s in suggestions)
    assert "recipe-quinoa" in [s["recipe_id"] for s in suggestions]


async def test_plan_create_add_summary_and_grocery(
    client: Client,
    sample_recipes: list[Recipe],
    sample_family_id: str,
) -> None:
    plan = await _call(
        client,
        "create_meal_plan",
        {"name": "Week 1", "start_date": "2026-04-06", "family_id": sample_family_id},
    )
    plan_id = plan["id"]
    assert plan["days"] == 7

    slots = await _call_list(
        client,
        "add_to_meal_plan",
        {
            "plan_id": plan_id,
            "day_offset": 0,
            "meal_type": "dinner",
            "recipe_id": "recipe-chicken",
            "servings": 2.0,
        },
    )
    assert [(s["recipe_id"], s["meal_type"]) for s in slots] == [("recipe-chicken", "dinner")]

    summary = await _call(
        client, "get_meal_plan_summary", {"plan_id": plan_id, "detail_level": "full"}
    )
    assert summary["plan_name"] == "Week 1"
    days = summary["daily_summaries"]
    assert isinstance(days, list)
    assert days[0]["member_macros"]["_default"]["calories"] == pytest.approx(560.0)
    assert days[0]["meals"]["dinner"] == [{"recipe_id": "recipe-chicken", "servings": 2.0}]

    weekly = await _call(
        client, "get_meal_plan_summary", {"plan_id": plan_id, "detail_level": "weekly"}
    )
    assert weekly["daily_summaries"] == []

    grocery = await _call(client, "generate_grocery_list", {"plan_id": plan_id})
    items = grocery["items"]
    assert isinstance(items, list)
    assert "chicken breast" in [i["name"] for i in items]


async def test_macro_targets_set_and_get(
    client: Client,
    sample_member_id: str,
) -> None:
    base: Json = {
        "member_id": sample_member_id,
        "calories": 2000,
        "protein_g": 150,
        "carbs_g": 200,
        "fat_g": 70,
    }
    first = await _call(client, "set_macro_target", {**base, "name": "Maintain"})
    second = await _call(client, "set_macro_target", {**base, "name": "Cut", "calories": 1800})
    assert first["id"] != second["id"]

    targets = await _call_list(client, "get_macro_targets", {"member_id": sample_member_id})
    assert [(t["name"], t["is_active"]) for t in targets] == [
        ("Maintain", False),
        ("Cut", True),
    ]
    assert targets[1]["calories"] == 1800.0

    # Non-active insert leaves the current active target alone.
    await _call(client, "set_macro_target", {**base, "name": "Bulk", "set_active": False})
    active = [t.name for t in await list_macro_targets(sample_member_id) if t.is_active]
    assert active == ["Cut"]

    assert await _call_list(client, "get_macro_targets", {"member_id": "nobody"}) == []


async def test_list_family_members(
    client: Client,
    sample_member_id: str,
    sample_family_id: str,
) -> None:
    members = await _call_list(client, "list_family_members", {"family_id": sample_family_id})
    assert len(members) == 1
    assert members[0]["id"] == sample_member_id
    assert members[0]["role"] == "admin"
    assert members[0]["is_default"] is True

    assert await _call_list(client, "list_family_members", {"family_id": "other"}) == []


# ── Error paths ──────────────────────────────────────────────────────────


async def test_get_recipe_detail_unknown_raises(client: Client) -> None:
    with pytest.raises(ToolError, match="Recipe not found: 'nope'"):
        await client.call_tool("get_recipe_detail", {"recipe_id": "nope"})


async def test_get_meal_plan_summary_unknown_raises(client: Client) -> None:
    with pytest.raises(ToolError, match="Meal plan not found: 'nope'"):
        await client.call_tool("get_meal_plan_summary", {"plan_id": "nope"})
