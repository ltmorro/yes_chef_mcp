"""Abstract base class for recipe providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class RawRecipe:
    """Provider-agnostic recipe data from an external source."""

    external_id: str
    name: str
    ingredients: list[RawIngredient] = field(default_factory=list)
    instructions: str = ""
    servings: int = 1
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    image_url: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RawIngredient:
    """A single ingredient as parsed from a provider."""

    name: str
    quantity: float | None = None
    unit: str | None = None
    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class GroceryPushItem:
    """An item to push to the provider's grocery list."""

    name: str
    quantity: float | None = None
    unit: str | None = None


class RecipeProvider(ABC):
    """Abstract interface for recipe data sources.

    Concrete providers implement authentication, recipe fetching,
    and optionally grocery list push-back.
    """

    @abstractmethod
    async def authenticate(self) -> None:
        """Authenticate with the provider. Raises on failure."""
        ...

    @abstractmethod
    async def fetch_recipes(
        self, since: datetime | None = None
    ) -> list[RawRecipe]:
        """Fetch recipes, optionally only those updated since a given time."""
        ...

    async def push_grocery_list(self, items: list[GroceryPushItem]) -> None:
        """Push a grocery list to the provider. Optional — not all providers support this."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support grocery list push"
        )
