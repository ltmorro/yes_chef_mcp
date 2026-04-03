"""Embedding generation using sentence-transformers.

Uses all-MiniLM-L6-v2 (384 dimensions) for recipe text embeddings.
The model runs locally — no external API calls.
"""

from __future__ import annotations

import logging

from mealmcp.core.models import Recipe

logger = logging.getLogger(__name__)

# Lazy-loaded model instance
_model: object | None = None


def _get_model() -> object:
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
    return _model


def build_recipe_text(recipe: Recipe) -> str:
    """Build the text representation used for embedding.

    Format: "{name}. Ingredients: {ingredient_names}. Tags: {tags}"
    """
    ingredient_names = ", ".join(ing.name for ing in recipe.ingredients)
    tags = ", ".join(recipe.tags) if recipe.tags else ""

    parts = [recipe.name]
    if ingredient_names:
        parts.append(f"Ingredients: {ingredient_names}")
    if tags:
        parts.append(f"Tags: {tags}")

    return ". ".join(parts)


def generate_embedding(recipe: Recipe) -> list[float]:
    """Generate a 384-dimensional embedding for a recipe."""
    from sentence_transformers import SentenceTransformer

    model = _get_model()
    assert isinstance(model, SentenceTransformer)

    text = build_recipe_text(recipe)
    embedding = model.encode(text, convert_to_numpy=True)
    return [float(x) for x in embedding.tolist()]


def generate_query_embedding(query: str) -> list[float]:
    """Generate a 384-dimensional embedding for a search query string."""
    from sentence_transformers import SentenceTransformer

    model = _get_model()
    assert isinstance(model, SentenceTransformer)

    embedding = model.encode(query, convert_to_numpy=True)
    return [float(x) for x in embedding.tolist()]


def generate_embeddings_batch(recipes: list[Recipe]) -> list[list[float]]:
    """Generate embeddings for multiple recipes in a batch."""
    from sentence_transformers import SentenceTransformer

    model = _get_model()
    assert isinstance(model, SentenceTransformer)

    texts = [build_recipe_text(r) for r in recipes]
    embeddings = model.encode(texts, convert_to_numpy=True, batch_size=32)
    return [[float(x) for x in emb.tolist()] for emb in embeddings]
