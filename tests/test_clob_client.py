import pytest
import httpx
from unittest.mock import AsyncMock, patch

from backend.crawler.clob_client import ClobClient

SAMPLE_BOOK = {
    "market": "token_yes_1",
    "asset_id": "token_yes_1",
    "bids": [
        {"price": "0.63", "size": "500"},
        {"price": "0.62", "size": "1000"},
    ],
    "asks": [
        {"price": "0.65", "size": "300"},
        {"price": "0.66", "size": "800"},
    ],
}

SAMPLE_PRICE = {"price": "0.65"}
SAMPLE_MIDPOINT = {"mid": "0.64"}
SAMPLE_SPREAD = {"spread": "0.02"}


@pytest.mark.asyncio
async def test_get_order_book():
    mock_resp = httpx.Response(200, json=SAMPLE_BOOK)
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = ClobClient()
        book = await client.get_order_book("token_yes_1")
        assert book["asset_id"] == "token_yes_1"
        assert len(book["bids"]) == 2
        assert len(book["asks"]) == 2


@pytest.mark.asyncio
async def test_get_price():
    mock_resp = httpx.Response(200, json=SAMPLE_PRICE)
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = ClobClient()
        price = await client.get_price("token_yes_1")
        assert price == 0.65


@pytest.mark.asyncio
async def test_get_midpoint():
    mock_resp = httpx.Response(200, json=SAMPLE_MIDPOINT)
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = ClobClient()
        mid = await client.get_midpoint("token_yes_1")
        assert mid == 0.64


@pytest.mark.asyncio
async def test_get_spread():
    mock_resp = httpx.Response(200, json=SAMPLE_SPREAD)
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = ClobClient()
        spread = await client.get_spread("token_yes_1")
        assert spread == 0.02
