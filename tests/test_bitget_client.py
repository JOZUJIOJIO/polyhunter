"""Tests for Bitget REST API client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from backend.exchanges.bitget.client import BitgetClient, BitgetAPIError


@pytest.fixture
def client():
    return BitgetClient(
        api_key="test-key",
        secret_key="test-secret",
        passphrase="test-pass",
    )


class TestBitgetClient:
    def test_sign_generates_base64(self, client):
        sig = client._sign("1234567890", "GET", "/api/v2/test")
        assert isinstance(sig, str)
        assert len(sig) > 0

    def test_headers_include_required_fields(self, client):
        headers = client._headers("GET", "/api/v2/test")
        assert "ACCESS-KEY" in headers
        assert "ACCESS-SIGN" in headers
        assert "ACCESS-TIMESTAMP" in headers
        assert "ACCESS-PASSPHRASE" in headers
        assert headers["ACCESS-KEY"] == "test-key"
        assert headers["ACCESS-PASSPHRASE"] == "test-pass"

    @pytest.mark.asyncio
    async def test_request_success(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": "00000", "data": {"balance": "100"}}

        with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_resp):
            result = await client._request("GET", "/api/v2/test")
            assert result == {"balance": "100"}

    @pytest.mark.asyncio
    async def test_request_api_error(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": "40001", "msg": "Invalid API key"}

        with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(BitgetAPIError) as exc_info:
                await client._request("GET", "/api/v2/test")
            assert "40001" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close(self, client):
        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_close:
            await client.close()
            mock_close.assert_called_once()
