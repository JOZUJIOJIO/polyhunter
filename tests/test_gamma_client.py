import pytest
import httpx
from unittest.mock import AsyncMock, patch

from backend.crawler.gamma_client import GammaClient

SAMPLE_EVENT = {
    "id": "event_1",
    "slug": "will-x-win",
    "title": "Will X win?",
    "markets": [
        {
            "id": "market_1",
            "conditionId": "cond_1",
            "question": "Will X win?",
            "slug": "will-x-win",
            "groupItemTitle": "X",
            "active": True,
            "closed": False,
            "clobTokenIds": '["token_yes_1", "token_no_1"]',
            "outcomePrices": '[0.65, 0.35]',
            "volume": "50000",
            "liquidityClob": "25000",
            "endDate": "2026-12-31T00:00:00Z",
            "tags": [{"label": "Politics"}],
        }
    ],
}


@pytest.mark.asyncio
async def test_fetch_active_events():
    mock_response = httpx.Response(200, json=[SAMPLE_EVENT])
    mock_response.request = httpx.Request("GET", "https://gamma-api.polymarket.com/events")
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_response):
        client = GammaClient()
        events = await client.fetch_active_events(limit=1)
        assert len(events) == 1
        assert events[0]["id"] == "event_1"


@pytest.mark.asyncio
async def test_parse_markets_from_event():
    client = GammaClient()
    markets = client.parse_markets(SAMPLE_EVENT)
    assert len(markets) == 1
    m = markets[0]
    assert m["id"] == "market_1"
    assert m["condition_id"] == "cond_1"
    assert m["token_id_yes"] == "token_yes_1"
    assert m["token_id_no"] == "token_no_1"
    assert m["question"] == "Will X win?"
    assert m["last_price_yes"] == 0.65
    assert m["last_price_no"] == 0.35
    assert m["category"] == "Politics"
    assert m["active"] is True
