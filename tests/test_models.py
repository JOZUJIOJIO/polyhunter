from datetime import datetime, timezone

from backend.db.models import Market, Signal, Trade, Position, PnlSnapshot


def test_create_market(db_session):
    market = Market(
        id="market_123",
        condition_id="cond_abc",
        token_id_yes="token_yes_1",
        token_id_no="token_no_1",
        question="Will X happen?",
        slug="will-x-happen",
        category="politics",
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        active=True,
        last_price_yes=0.65,
        last_price_no=0.35,
        volume_24h=50000.0,
        liquidity=25000.0,
    )
    db_session.add(market)
    db_session.commit()

    result = db_session.query(Market).first()
    assert result.id == "market_123"
    assert result.question == "Will X happen?"
    assert result.last_price_yes == 0.65
    assert result.active is True


def test_create_signal(db_session):
    market = Market(
        id="m1",
        condition_id="c1",
        token_id_yes="ty1",
        token_id_no="tn1",
        question="Test?",
        active=True,
    )
    db_session.add(market)
    db_session.commit()

    signal = Signal(
        market_id="m1",
        type="ARBITRAGE",
        source_detail='{"yes_price": 0.45, "no_price": 0.53}',
        current_price=0.45,
        fair_value=0.50,
        edge_pct=2.5,
        confidence=90,
        status="NEW",
    )
    db_session.add(signal)
    db_session.commit()

    result = db_session.query(Signal).first()
    assert result.type == "ARBITRAGE"
    assert result.edge_pct == 2.5
    assert result.market.question == "Test?"


def test_create_trade(db_session):
    market = Market(id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1", question="T?", active=True)
    db_session.add(market)
    db_session.commit()

    trade = Trade(
        market_id="m1",
        token_id="ty1",
        side="BUY",
        price=0.45,
        size=100.0,
        cost=45.90,
        status="FILLED",
        order_id="order_xyz",
    )
    db_session.add(trade)
    db_session.commit()

    result = db_session.query(Trade).first()
    assert result.side == "BUY"
    assert result.cost == 45.90


def test_create_position(db_session):
    market = Market(id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1", question="T?", active=True)
    db_session.add(market)
    db_session.commit()

    pos = Position(
        market_id="m1",
        token_id="ty1",
        side="YES",
        avg_entry_price=0.45,
        size=100.0,
        current_price=0.55,
        unrealized_pnl=10.0,
    )
    db_session.add(pos)
    db_session.commit()

    result = db_session.query(Position).first()
    assert result.unrealized_pnl == 10.0


def test_create_pnl_snapshot(db_session):
    from datetime import date

    snap = PnlSnapshot(
        date=date(2026, 4, 7),
        total_value=5000.0,
        realized_pnl=150.0,
        unrealized_pnl=30.0,
        num_trades=12,
        win_rate=0.58,
    )
    db_session.add(snap)
    db_session.commit()

    result = db_session.query(PnlSnapshot).first()
    assert result.total_value == 5000.0
    assert result.win_rate == 0.58
