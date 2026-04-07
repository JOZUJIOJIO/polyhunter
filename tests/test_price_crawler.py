import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Market
from backend.crawler.price_crawler import PriceCrawler


@pytest.fixture
def price_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    m = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True, last_price_yes=0.50, last_price_no=0.50,
    )
    session.add(m)
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_update_prices(price_db):
    mock_prices = {"ty1": 0.65, "tn1": 0.35}
    with patch(
        "backend.crawler.price_crawler.ClobClient.get_prices_batch",
        new_callable=AsyncMock,
        return_value=mock_prices,
    ):
        crawler = PriceCrawler(session=price_db)
        updated = await crawler.update_prices()
        assert updated == 1

        market = price_db.query(Market).first()
        assert market.last_price_yes == 0.65
        assert market.last_price_no == 0.35


@pytest.mark.asyncio
async def test_update_prices_skips_inactive(price_db):
    market = price_db.query(Market).first()
    market.active = False
    price_db.commit()

    with patch(
        "backend.crawler.price_crawler.ClobClient.get_prices_batch",
        new_callable=AsyncMock,
        return_value={},
    ):
        crawler = PriceCrawler(session=price_db)
        updated = await crawler.update_prices()
        assert updated == 0
