"""Tests for embedding model loading when the model can't be fetched."""

from __future__ import annotations

import sys
import types

import pytest

from yes_chef_mcp.pipeline import embeddings


class _OfflineModel:
    """Stands in for SentenceTransformer: every construction fails like HF offline."""

    attempts = 0

    def __init__(self, name: str) -> None:
        type(self).attempts += 1
        raise OSError(f"We couldn't connect to 'https://huggingface.co' to load {name}")


@pytest.fixture(autouse=True)
def _offline_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _OfflineModel.attempts = 0
    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = _OfflineModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    monkeypatch.setattr(embeddings, "_model", None)
    monkeypatch.setattr(embeddings, "_load_failed_at", None)


def test_failed_load_is_not_retried_on_every_call() -> None:
    for _ in range(3):
        with pytest.raises(embeddings.EmbeddingModelUnavailableError):
            embeddings.generate_query_embedding("chicken")

    assert _OfflineModel.attempts == 1


def test_failed_load_is_retried_after_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embeddings, "RETRY_AFTER_SECONDS", 0.0)

    for _ in range(2):
        with pytest.raises(embeddings.EmbeddingModelUnavailableError):
            embeddings.generate_query_embedding("chicken")

    assert _OfflineModel.attempts == 2


def test_unavailable_model_is_an_oserror() -> None:
    # Callers that already fall back on OSError keep working.
    assert issubclass(embeddings.EmbeddingModelUnavailableError, OSError)
