import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings
from backend.db.models import Base, Market, Trade, Position
from backend.trader.risk_manager import RiskManager, RiskCheckResult


@pytest.fixture
def risk_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True, last_price_yes=0.50, last_price_no=0.50,
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )
    session.add(market)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_passes_when_within_limits(risk_db):
    settings = Settings(RISK_MAX_SINGLE_BET_PCT=10, RISK_MAX_DAILY_LOSS_PCT=5, RISK_MAX_POSITION_PCT=20, RISK_MAX_POSITIONS=10)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=50.0, price=0.50)
    assert result.approved is True
    assert result.reason == ""


def test_rejects_exceeding_single_bet(risk_db):
    settings = Settings(RISK_MAX_SINGLE_BET_PCT=10)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=150.0, price=0.50)
    assert result.approved is True
    result = rm.check_order(market_id="m1", side="BUY", size=250.0, price=0.50)
    assert result.approved is False
    assert "single bet" in result.reason.lower()


def test_rejects_exceeding_position_concentration(risk_db):
    pos = Position(market_id="m1", token_id="ty1", side="YES", avg_entry_price=0.50, size=300.0, current_price=0.50, unrealized_pnl=0.0)
    risk_db.add(pos)
    risk_db.commit()
    settings = Settings(RISK_MAX_POSITION_PCT=20)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=100.0, price=0.50)
    assert result.approved is True
    result = rm.check_order(market_id="m1", side="BUY", size=150.0, price=0.50)
    assert result.approved is False
    assert "concentration" in result.reason.lower()


def test_rejects_exceeding_max_positions(risk_db):
    for i in range(10):
        m = Market(id=f"mx{i}", condition_id=f"cx{i}", token_id_yes=f"tyx{i}", token_id_no=f"tnx{i}", question=f"Q{i}?", active=True)
        risk_db.add(m)
        pos = Position(market_id=f"mx{i}", token_id=f"tyx{i}", side="YES", avg_entry_price=0.50, size=10.0, current_price=0.50, unrealized_pnl=0.0)
        risk_db.add(pos)
    risk_db.commit()
    settings = Settings(RISK_MAX_POSITIONS=10)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=10000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=10.0, price=0.50)
    assert result.approved is False
    assert "max positions" in result.reason.lower()


def test_rejects_near_expiry(risk_db):
    market = risk_db.get(Market, "m1")
    market.end_date = datetime.now(timezone.utc) + timedelta(hours=12)
    risk_db.commit()
    settings = Settings(RISK_EXPIRY_BUFFER_HOURS=24)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=10.0, price=0.50)
    assert result.approved is False
    assert "expir" in result.reason.lower()


def test_rejects_exceeding_daily_loss(risk_db):
    for i in range(3):
        trade = Trade(market_id="m1", token_id="ty1", side="BUY", price=0.50, size=100.0, cost=50.0, status="FILLED", pnl=-20.0)
        risk_db.add(trade)
    risk_db.commit()
    settings = Settings(RISK_MAX_DAILY_LOSS_PCT=5)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=10.0, price=0.50)
    assert result.approved is False
    assert "daily loss" in result.reason.lower()
