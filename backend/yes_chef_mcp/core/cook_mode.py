"""Cook mode: recipe instructions as steps, scaled ingredients, and the meal log."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace
from datetime import datetime

from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.models import CookRating, CookStep, Ingredient, MealLogEntry, MealType

# Leading step markers: "1.", "2)", "3:", "Step 4:", "Step 5 -", or a bullet.
# "(?!\d)" keeps a quantity like "1.5 cups" from being read as step 1.
_STEP_PREFIX = re.compile(r"^(?:step\s*\d+\s*[.:)-]?|\d+\s*[.:)](?!\d)|[-*•])\s*", re.IGNORECASE)

# Where to split one long paragraph: after a sentence end, before a capital or "2. ".
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z]|\d+[.)]\s)")

_FRACTIONS: dict[str, str] = {"½": ".5", "¼": ".25", "¾": ".75", "⅓": ".33", "⅔": ".67"}

_NUMBER = r"\d+(?:\.\d+)?"
_UNIT_SECONDS: dict[str, int] = {"h": 3600, "m": 60, "s": 1}

# "20 minutes", "1 hr", "10-12 mins", "5 to 7 minutes", "30 seconds".
# The unit's first letter picks the multiplier from _UNIT_SECONDS.
_DURATION = re.compile(
    rf"({_NUMBER})(?:\s*(?:-|\u2013|to)\s*({_NUMBER}))?\s*"
    r"(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b",
    re.IGNORECASE,
)


def split_steps(instructions: str) -> list[str]:
    """Split free-form instructions into steps.

    One step per non-blank line, with numbering and bullets stripped. A
    single paragraph is split into sentences instead, so "Cook pasta. Drain
    it." still gives two steps.
    """
    lines = [line.strip() for line in instructions.splitlines() if line.strip()]
    if len(lines) == 1:
        lines = _SENTENCE_BREAK.split(lines[0])

    steps = [_STEP_PREFIX.sub("", line).strip() for line in lines]
    return [step for step in steps if step]


def parse_timer_seconds(text: str) -> int | None:
    """The first duration in a step, in seconds, or None if it has none.

    Ranges use the upper bound ("10-12 minutes" is 12 minutes), and an hour
    count directly followed by minutes is combined ("1 hour 15 minutes").
    """
    for fraction, decimal in _FRACTIONS.items():
        text = text.replace(fraction, decimal)

    matches = list(_DURATION.finditer(text))
    if not matches:
        return None

    def seconds(match: re.Match[str]) -> float:
        amount = float(match.group(2) or match.group(1))
        return amount * _UNIT_SECONDS[match.group(3)[0].lower()]

    first = matches[0]
    total = seconds(first)
    if len(matches) > 1 and first.group(3)[0].lower() == "h":
        follow = matches[1]
        between = text[first.end() : follow.start()].strip(" ,").lower()
        if follow.group(3)[0].lower() == "m" and between in ("", "and"):
            total += seconds(follow)

    return round(total) or None


def cook_steps(instructions: str) -> list[CookStep]:
    """Numbered steps with any timer found in each."""
    return [
        CookStep(index=i, text=text, timer_seconds=parse_timer_seconds(text))
        for i, text in enumerate(split_steps(instructions), start=1)
    ]


def scale_ingredients(ingredients: list[Ingredient], factor: float) -> list[Ingredient]:
    """Multiply every known quantity by factor (unquantified items are left as is)."""
    return [
        replace(ing, quantity=round(ing.quantity * factor, 2)) if ing.quantity is not None else ing
        for ing in ingredients
    ]


async def log_cooked_meal(
    recipe_id: str,
    servings: float,
    rating: CookRating | None = None,
    plan_id: str | None = None,
    day_offset: int | None = None,
    meal_type: MealType | None = None,
) -> MealLogEntry:
    """Record that a recipe was cooked. Always inserts a new entry."""
    entry = MealLogEntry(
        id=str(uuid.uuid4()),
        recipe_id=recipe_id,
        servings=servings,
        cooked_at=datetime.now(),
        rating=rating,
        plan_id=plan_id,
        day_offset=day_offset,
        meal_type=meal_type,
    )
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO meal_log (id, recipe_id, plan_id, day_offset, meal_type,
                                  servings, rating, cooked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                recipe_id,
                plan_id,
                day_offset,
                meal_type.value if meal_type else None,
                servings,
                rating.value if rating else None,
                entry.cooked_at.isoformat(),
            ),
        )
    return entry
