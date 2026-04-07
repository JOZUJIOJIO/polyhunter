import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Market
from backend.crawler.market_crawler import MarketCrawler

PARSED_MARKET = {
    "id": "m1",
    "condition_id": "c1",
    "token_id_yes": "ty1",
    "token_id_no": "tn1",
    "question": "Will X happen?",
    "slug": "will-x-happen",
    "category": "Politics",
    "end_date": "2026-12-31T00:00:00Z",
    "active": True,
    "last_price_yes": 0.65,
    "last_price_no": 0.35,
    "volume_24h": 50000.0,
    "liquidity": 25000.0,
}


@pytest.fixture
def crawler_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_sync_markets_inserts_new(crawler_db):
    mock_event = {"id": "e1", "markets": []}
    with (
        patch.object(
            MarketCrawler, "_fetch_all_events", new_callable=AsyncMock, return_value=[mock_event]
        ),
        patch.object(
            MarketCrawler, "_parse_all_markets", return_value=[PARSED_MARKET]
        ),
    ):
        crawler = MarketCrawler(session=crawler_db)
        count = await crawler.sync_markets()
        assert count == 1

        market = crawler_db.query(Market).first()
        assert market.id == "m1"
        assert market.question == "Will X happen?"
        assert market.last_price_yes == 0.65


@pytest.mark.asyncio
async def test_sync_markets_updates_existing(crawler_db):
    existing = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Will X happen?", active=True, last_price_yes=0.50, last_price_no=0.50,
    )
    crawler_db.add(existing)
    crawler_db.commit()

    updated = {**PARSED_MARKET, "last_price_yes": 0.70, "last_price_no": 0.30}
    with (
        patch.object(MarketCrawler, "_fetch_all_events", new_callable=AsyncMock, return_value=[]),
        patch.object(MarketCrawler, "_parse_all_markets", return_value=[updated]),
    ):
        crawler = MarketCrawler(session=crawler_db)
        count = await crawler.sync_markets()
        assert count == 1

        market = crawler_db.query(Market).first()
        assert market.last_price_yes == 0.70
        assert market.last_price_no == 0.30
