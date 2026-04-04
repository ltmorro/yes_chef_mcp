"""Tests for the AnyList recipe provider."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from mealmcp.pipeline.providers.anylist import AnyListAuthError, AnyListProvider
from mealmcp.pipeline.providers.base import GroceryPushItem


@pytest.fixture()
def provider() -> AnyListProvider:
    return AnyListProvider(email="chef@example.com", password="s3cret")


_FAKE_REQUEST = httpx.Request("POST", "https://www.anylist.com/auth/token")


def _token_response(
    status_code: int = 200,
    access_token: str = "tok_abc123",
    refresh_token: str = "ref_xyz789",
) -> httpx.Response:
    """Build a fake /auth/token response."""
    if status_code == 401:
        return httpx.Response(
            status_code=401,
            json={"error": "unauthorized"},
            request=_FAKE_REQUEST,
        )
    return httpx.Response(
        status_code=status_code,
        json={"access_token": access_token, "refresh_token": refresh_token},
        request=_FAKE_REQUEST,
    )


class TestAuthenticate:
    async def test_successful_auth(self, provider: AnyListProvider) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _token_response()
        provider._client = mock_client

        await provider.authenticate()

        mock_client.post.assert_called_once_with(
            "/auth/token",
            data={"email": "chef@example.com", "password": "s3cret"},
        )
        assert provider._access_token == "tok_abc123"
        assert provider._refresh_token == "ref_xyz789"

    async def test_invalid_credentials(self, provider: AnyListProvider) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _token_response(status_code=401)
        provider._client = mock_client

        with pytest.raises(AnyListAuthError, match="Invalid AnyList credentials"):
            await provider.authenticate()

    async def test_server_error_raises(self, provider: AnyListProvider) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(status_code=500, request=_FAKE_REQUEST)
        provider._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await provider.authenticate()


class TestAuthHeaders:
    def test_headers_before_auth(self, provider: AnyListProvider) -> None:
        with pytest.raises(AnyListAuthError, match="Not authenticated"):
            provider._auth_headers()

    async def test_headers_after_auth(self, provider: AnyListProvider) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _token_response()
        provider._client = mock_client

        await provider.authenticate()
        headers = provider._auth_headers()

        assert headers["Authorization"] == "Bearer tok_abc123"
        assert "X-AnyLeaf-Client-Identifier" in headers
        assert headers["X-AnyLeaf-API-Version"] == "3"


class TestFetchRecipes:
    async def test_raises_not_implemented(self, provider: AnyListProvider) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _token_response()
        provider._client = mock_client

        with pytest.raises(NotImplementedError, match="protobuf"):
            await provider.fetch_recipes()

    async def test_authenticates_first(self, provider: AnyListProvider) -> None:
        """fetch_recipes triggers authentication if not yet authenticated."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _token_response()
        provider._client = mock_client

        with pytest.raises(NotImplementedError):
            await provider.fetch_recipes()

        # Authentication should have been called
        assert provider._access_token == "tok_abc123"


class TestPushGroceryList:
    async def test_raises_not_implemented(self, provider: AnyListProvider) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _token_response()
        provider._client = mock_client

        items = [GroceryPushItem(name="milk", quantity=1.0, unit="gallon")]
        with pytest.raises(NotImplementedError, match="protobuf"):
            await provider.push_grocery_list(items)


class TestClose:
    async def test_close_client(self, provider: AnyListProvider) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        provider._client = mock_client

        await provider.close()

        mock_client.aclose.assert_called_once()
        assert provider._client is None

    async def test_close_noop_when_no_client(self, provider: AnyListProvider) -> None:
        await provider.close()  # should not raise
