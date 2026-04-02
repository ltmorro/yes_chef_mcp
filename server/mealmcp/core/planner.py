"""Meal plan CRUD operations."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime

from mealmcp.core.db import get_cursor
from mealmcp.core.models import (
    MealPlan,
    MealSlot,
    MealType,
)


def create_meal_plan(
    family_id: str,
    name: str,
    start_date: date,
    days: int = 7,
) -> MealPlan:
    """Create an empty meal plan."""
    plan_id = str(uuid.uuid4())
    now = datetime.now()

    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO meal_plans (id, family_id, name, start_date, days, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (plan_id, family_id, name, start_date.isoformat(), days, now.isoformat()),
        )

    return MealPlan(
        id=plan_id,
        family_id=family_id,
        name=name,
        start_date=start_date,
        days=days,
        created_at=now,
    )


def get_meal_plan(plan_id: str) -> MealPlan | None:
    """Fetch a meal plan by ID."""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM meal_plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()
        if row is None:
            return None

        created_str = row["created_at"]
        return MealPlan(
            id=str(row["id"]),
            family_id=str(row["family_id"]),
            name=str(row["name"]),
            start_date=date.fromisoformat(str(row["start_date"])),
            days=int(str(row["days"])),
            created_at=(
                datetime.fromisoformat(str(created_str)) if created_str else None
            ),
        )


def list_meal_plans(family_id: str | None = None) -> list[MealPlan]:
    """List meal plans, optionally filtered by family."""
    condition = " WHERE family_id = ?" if family_id else ""
    params: list[str] = [family_id] if family_id else []

    with get_cursor() as cursor:
        cursor.execute(
            f"SELECT * FROM meal_plans{condition} ORDER BY start_date DESC",
            params,
        )
        rows = cursor.fetchall()

    plans: list[MealPlan] = []
    for row in rows:
        created_str = row["created_at"]
        plans.append(
            MealPlan(
                id=str(row["id"]),
                family_id=str(row["family_id"]),
                name=str(row["name"]),
                start_date=date.fromisoformat(str(row["start_date"])),
                days=int(str(row["days"])),
                created_at=(
                    datetime.fromisoformat(str(created_str)) if created_str else None
                ),
            )
        )
    return plans


def add_meal_slot(
    plan_id: str,
    day_offset: int,
    meal_type: MealType,
    recipe_id: str,
    servings: float = 1.0,
    member_servings: dict[str, float] | None = None,
) -> MealSlot:
    """Add a recipe to a meal plan slot."""
    ms = member_servings or {}
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO meal_slots (plan_id, day_offset, meal_type, recipe_id,
                                    servings, member_servings)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id, day_offset, meal_type, recipe_id) DO UPDATE SET
                servings=excluded.servings,
                member_servings=excluded.member_servings
            """,
            (plan_id, day_offset, meal_type.value, recipe_id, servings, json.dumps(ms)),
        )

    return MealSlot(
        plan_id=plan_id,
        day_offset=day_offset,
        meal_type=meal_type,
        recipe_id=recipe_id,
        servings=servings,
        member_servings=ms,
    )


def get_meal_slots(
    plan_id: str,
    day_offset: int | None = None,
) -> list[MealSlot]:
    """Get all meal slots for a plan, optionally filtered by day."""
    conditions = ["plan_id = ?"]
    params: list[str | int] = [plan_id]

    if day_offset is not None:
        conditions.append("day_offset = ?")
        params.append(day_offset)

    where = " AND ".join(conditions)

    with get_cursor() as cursor:
        cursor.execute(
            f"SELECT * FROM meal_slots WHERE {where} ORDER BY day_offset, meal_type",
            params,
        )
        rows = cursor.fetchall()

    return [
        MealSlot(
            plan_id=str(row["plan_id"]),
            day_offset=int(str(row["day_offset"])),
            meal_type=MealType(str(row["meal_type"])),
            recipe_id=str(row["recipe_id"]),
            servings=float(str(row["servings"])),
            member_servings=json.loads(str(row["member_servings"])),
        )
        for row in rows
    ]


def remove_meal_slot(
    plan_id: str,
    day_offset: int,
    meal_type: MealType,
    recipe_id: str,
) -> bool:
    """Remove a recipe from a meal plan slot. Returns True if removed."""
    with get_cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM meal_slots
            WHERE plan_id = ? AND day_offset = ? AND meal_type = ? AND recipe_id = ?
            """,
            (plan_id, day_offset, meal_type.value, recipe_id),
        )
        return cursor.rowcount > 0


def delete_meal_plan(plan_id: str) -> bool:
    """Delete a meal plan and all its slots. Returns True if deleted."""
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM meal_slots WHERE plan_id = ?", (plan_id,))
        cursor.execute("DELETE FROM meal_plans WHERE id = ?", (plan_id,))
        return cursor.rowcount > 0
