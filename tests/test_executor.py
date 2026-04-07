import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings
from backend.db.models import Base, Market, Signal, Trade
from backend.trader.executor import OrderExecutor
from backend.trader.risk_manager import RiskCheckResult


@pytest.fixture
def exec_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    market = Market(id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1", question="Test?", active=True, last_price_yes=0.50, last_price_no=0.50)
    session.add(market)
    signal = Signal(id=1, market_id="m1", type="ARBITRAGE", current_price=0.50, edge_pct=3.0, confidence=90, status="NEW")
    session.add(signal)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_execute_order_success(exec_db):
    mock_risk = MagicMock()
    mock_risk.check_order.return_value = RiskCheckResult(approved=True)
    executor = OrderExecutor(session=exec_db, risk_manager=mock_risk)
    with patch.object(executor, "_submit_order", return_value="order_abc"):
        trade = executor.execute(signal_id=1, market_id="m1", token_id="ty1", side="BUY", price=0.50, size=100.0)
    assert trade.status == "FILLED"
    assert trade.order_id == "order_abc"
    assert trade.cost == 50.0
    saved = exec_db.query(Trade).first()
    assert saved.order_id == "order_abc"
    signal = exec_db.query(Signal).get(1)
    assert signal.status == "ACTED"


def test_execute_order_rejected_by_risk(exec_db):
    mock_risk = MagicMock()
    mock_risk.check_order.return_value = RiskCheckResult(approved=False, reason="Too risky")
    executor = OrderExecutor(session=exec_db, risk_manager=mock_risk)
    trade = executor.execute(signal_id=1, market_id="m1", token_id="ty1", side="BUY", price=0.50, size=100.0)
    assert trade is None
    assert exec_db.query(Trade).count() == 0


def test_execute_order_submission_fails(exec_db):
    mock_risk = MagicMock()
    mock_risk.check_order.return_value = RiskCheckResult(approved=True)
    executor = OrderExecutor(session=exec_db, risk_manager=mock_risk)
    with patch.object(executor, "_submit_order", side_effect=Exception("API error")):
        trade = executor.execute(signal_id=1, market_id="m1", token_id="ty1", side="BUY", price=0.50, size=100.0)
    assert trade.status == "CANCELLED"
    saved = exec_db.query(Trade).first()
    assert saved.status == "CANCELLED"
