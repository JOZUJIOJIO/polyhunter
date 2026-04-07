import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Market, Trade, Position, PnlSnapshot
from backend.trader.position_tracker import PositionTracker


@pytest.fixture
def tracker_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    market = Market(id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1", question="Test?", active=True, last_price_yes=0.60, last_price_no=0.40)
    session.add(market)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_update_position_from_buy_trade(tracker_db):
    trade = Trade(market_id="m1", token_id="ty1", side="BUY", price=0.50, size=100.0, cost=50.0, status="FILLED")
    tracker_db.add(trade)
    tracker_db.commit()
    tracker = PositionTracker(session=tracker_db)
    tracker.update_from_trade(trade)
    pos = tracker_db.query(Position).first()
    assert pos is not None
    assert pos.market_id == "m1"
    assert pos.side == "YES"
    assert pos.avg_entry_price == 0.50
    assert pos.size == 100.0


def test_update_position_averages_price(tracker_db):
    pos = Position(market_id="m1", token_id="ty1", side="YES", avg_entry_price=0.40, size=100.0, current_price=0.50, unrealized_pnl=10.0)
    tracker_db.add(pos)
    tracker_db.commit()
    trade = Trade(market_id="m1", token_id="ty1", side="BUY", price=0.60, size=100.0, cost=60.0, status="FILLED")
    tracker_db.add(trade)
    tracker_db.commit()
    tracker = PositionTracker(session=tracker_db)
    tracker.update_from_trade(trade)
    pos = tracker_db.query(Position).first()
    assert pos.size == 200.0
    assert pos.avg_entry_price == pytest.approx(0.50)


def test_refresh_unrealized_pnl(tracker_db):
    pos = Position(market_id="m1", token_id="ty1", side="YES", avg_entry_price=0.40, size=100.0, current_price=0.50, unrealized_pnl=0.0)
    tracker_db.add(pos)
    tracker_db.commit()
    tracker = PositionTracker(session=tracker_db)
    tracker.refresh_pnl()
    pos = tracker_db.query(Position).first()
    assert pos.current_price == 0.60
    assert pos.unrealized_pnl == pytest.approx(20.0)


def test_take_pnl_snapshot(tracker_db):
    pos = Position(market_id="m1", token_id="ty1", side="YES", avg_entry_price=0.40, size=100.0, current_price=0.60, unrealized_pnl=20.0)
    tracker_db.add(pos)
    trade = Trade(market_id="m1", token_id="ty1", side="BUY", price=0.40, size=100.0, cost=40.0, status="FILLED", pnl=15.0)
    tracker_db.add(trade)
    tracker_db.commit()
    tracker = PositionTracker(session=tracker_db, total_balance=1000.0)
    snapshot = tracker.take_snapshot()
    assert snapshot.total_value > 0
    assert snapshot.unrealized_pnl == 20.0
    assert snapshot.realized_pnl == 15.0
    assert snapshot.num_trades == 1
