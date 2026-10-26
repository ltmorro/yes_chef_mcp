"""Tests for core.members macro-target queries."""

from __future__ import annotations

import pytest

from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.members import create_macro_target, get_active_macro_target

MEMBER_ID = "member-test-1"


@pytest.fixture()
async def member_id(sample_family_id: str) -> str:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO members (id, family_id, name, role, is_default) VALUES (?, ?, ?, ?, ?)",
            (MEMBER_ID, sample_family_id, "Alex", "admin", 1),
        )
    return MEMBER_ID


async def test_active_target_none_without_targets(member_id: str) -> None:
    assert await get_active_macro_target(member_id) is None


async def test_active_target_ignores_inactive(member_id: str) -> None:
    await create_macro_target(member_id, "Old", 2000, 150, 200, 60, set_active=False)
    assert await get_active_macro_target(member_id) is None


async def test_active_target_follows_latest_save(member_id: str) -> None:
    await create_macro_target(member_id, "Maintain", 2200, 150, 250, 70)
    await create_macro_target(member_id, "Cut", 1900, 170, 180, 60)

    active = await get_active_macro_target(member_id)

    assert active is not None
    assert active.name == "Cut"
    assert active.calories == 1900


async def test_active_target_oldest_wins_with_legacy_duplicates(member_id: str) -> None:
    await create_macro_target(member_id, "First", 2000, 150, 200, 60)
    # Legacy data: a second active row inserted without deactivating the first
    await create_macro_target(member_id, "Second", 2100, 150, 220, 60, set_active=False)
    async with get_db() as db:
        await db.execute("UPDATE macro_targets SET is_active = 1 WHERE name = 'Second'")

    active = await get_active_macro_target(member_id)

    assert active is not None
    assert active.name == "First"
