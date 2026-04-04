"""AnyList recipe provider.

Connects to AnyList's API to fetch recipes and push grocery lists.
AnyList uses a proprietary protocol with protobuf-encoded data payloads.
Authentication uses standard HTTP form-encoded requests.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

import httpx

from mealmcp.pipeline.providers.base import (
    GroceryPushItem,
    RawRecipe,
    RecipeProvider,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.anylist.com"
_API_VERSION = "3"


class AnyListAuthError(Exception):
    """Raised when AnyList authentication fails."""


class AnyListProvider(RecipeProvider):
    """Recipe provider for AnyList.

    Authentication is fully implemented via AnyList's token endpoint.
    Recipe fetch and grocery push require protobuf encoding/decoding
    and raise ``NotImplementedError`` until protobuf support is added.
    """

    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password
        self._client_id: str = str(uuid.uuid4()).upper()
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Build headers required for authenticated AnyList requests."""
        if self._access_token is None:
            raise AnyListAuthError("Not authenticated — call authenticate() first")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "X-AnyLeaf-Client-Identifier": self._client_id,
            "X-AnyLeaf-API-Version": _API_VERSION,
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0)
        return self._client

    # ------------------------------------------------------------------
    # RecipeProvider interface
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Authenticate with AnyList via email/password.

        Obtains an access token and refresh token from the ``/auth/token``
        endpoint. Raises :class:`AnyListAuthError` on failure.
        """
        client = await self._ensure_client()

        response = await client.post(
            "/auth/token",
            data={"email": self._email, "password": self._password},
        )

        if response.status_code == 401:
            raise AnyListAuthError("Invalid AnyList credentials")
        response.raise_for_status()

        body: dict[str, str] = response.json()
        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token", "")
        logger.info("AnyList authentication successful")

    async def fetch_recipes(self, since: datetime | None = None) -> list[RawRecipe]:
        """Fetch recipes from AnyList.

        AnyList returns recipe data as protobuf-encoded binary from
        ``POST /data/user-data/get``. Full decoding requires the AnyList
        protobuf schema definitions.

        Raises:
            NotImplementedError: Protobuf decoding is not yet implemented.
        """
        if self._access_token is None:
            await self.authenticate()

        raise NotImplementedError(
            "AnyList recipe fetch requires protobuf decoding — not yet implemented. "
            "See https://github.com/codetheweb/anylist for protocol details."
        )

    async def push_grocery_list(self, items: list[GroceryPushItem]) -> None:
        """Push grocery list items to AnyList.

        AnyList expects protobuf-encoded ``PBListOperationList`` payloads
        posted to ``POST /data/shopping-lists/update``.

        Raises:
            NotImplementedError: Protobuf encoding is not yet implemented.
        """
        if self._access_token is None:
            await self.authenticate()

        raise NotImplementedError(
            "AnyList grocery push requires protobuf encoding — not yet implemented. "
            "See https://github.com/codetheweb/anylist for protocol details."
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
