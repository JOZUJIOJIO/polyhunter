import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings
from backend.db.models import Base, Market, Signal
from backend.signals.arbitrage import ArbitrageDetector


@pytest.fixture
def arb_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def test_detects_yes_no_mispricing(arb_db):
    """YES + NO < 1.0 means buying both locks profit."""
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.45, last_price_no=0.50,  # sum = 0.95, gap = 5%
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()

    assert len(signals) == 1
    s = signals[0]
    assert s.type == "ARBITRAGE"
    assert s.market_id == "m1"
    assert s.edge_pct > 0
    detail = json.loads(s.source_detail)
    assert detail["yes_price"] == 0.45
    assert detail["no_price"] == 0.50


def test_no_signal_when_fairly_priced(arb_db):
    """YES + NO = 1.0 means no arbitrage."""
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.60, last_price_no=0.40,  # sum = 1.0
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()

    assert len(signals) == 0


def test_no_signal_when_edge_too_small(arb_db):
    """Edge exists but is smaller than fee + min_edge threshold."""
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.49, last_price_no=0.50,  # sum = 0.99, gap = 1%
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()

    assert len(signals) == 0


def test_skips_inactive_markets(arb_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=False,
        last_price_yes=0.30, last_price_no=0.30,
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()

    assert len(signals) == 0


def test_saves_signals(arb_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.40, last_price_no=0.45,
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()
    count = detector.save_signals(signals)

    assert count == 1
    saved = arb_db.query(Signal).first()
    assert saved.status == "NEW"
    assert saved.type == "ARBITRAGE"
