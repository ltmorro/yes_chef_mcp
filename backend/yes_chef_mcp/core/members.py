"""Family members and their macro targets."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.models import MacroTarget, Member, MemberRole


def _row_to_member(row: sqlite3.Row) -> Member:
    created_str = row["created_at"]
    return Member(
        id=str(row["id"]),
        family_id=str(row["family_id"]),
        name=str(row["name"]),
        role=MemberRole(str(row["role"])),
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(str(created_str)) if created_str else None,
    )


def _row_to_target(row: sqlite3.Row) -> MacroTarget:
    return MacroTarget(
        id=str(row["id"]),
        member_id=str(row["member_id"]),
        name=str(row["name"]),
        calories=float(str(row["calories"])),
        protein_g=float(str(row["protein_g"])),
        carbs_g=float(str(row["carbs_g"])),
        fat_g=float(str(row["fat_g"])),
        is_active=bool(row["is_active"]),
    )


async def list_members(family_id: str | None = None) -> list[Member]:
    """List members, optionally filtered by family, in insertion order."""
    condition = " WHERE family_id = ?" if family_id else ""
    params: list[str] = [family_id] if family_id else []

    async with (
        get_db() as db,
        db.execute(f"SELECT * FROM members{condition} ORDER BY rowid", params) as cursor,
    ):
        rows = await cursor.fetchall()

    return [_row_to_member(row) for row in rows]


async def list_macro_targets(member_id: str | None = None) -> list[MacroTarget]:
    """List macro targets, optionally filtered by member, in insertion order."""
    condition = " WHERE member_id = ?" if member_id else ""
    params: list[str] = [member_id] if member_id else []

    async with (
        get_db() as db,
        db.execute(f"SELECT * FROM macro_targets{condition} ORDER BY rowid", params) as cursor,
    ):
        rows = await cursor.fetchall()

    return [_row_to_target(row) for row in rows]


async def create_macro_target(
    member_id: str,
    name: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    set_active: bool = True,
) -> MacroTarget:
    """Insert a new macro target for a member.

    Always creates a new row (existing targets are never edited). When
    set_active is true, the member's other targets are deactivated first so
    the new one becomes the only active target.
    """
    target = MacroTarget(
        id=str(uuid.uuid4()),
        member_id=member_id,
        name=name,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        is_active=set_active,
    )

    async with get_db() as db:
        if set_active:
            await db.execute(
                "UPDATE macro_targets SET is_active = 0 WHERE member_id = ?",
                (member_id,),
            )

        await db.execute(
            """
            INSERT INTO macro_targets (id, member_id, name, calories, protein_g,
                                       carbs_g, fat_g, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target.id,
                target.member_id,
                target.name,
                target.calories,
                target.protein_g,
                target.carbs_g,
                target.fat_g,
                int(target.is_active),
            ),
        )

    return target
