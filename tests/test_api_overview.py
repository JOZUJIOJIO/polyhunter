from backend.db.models import Market, Signal, Position


def test_overview_empty(test_app):
    client, _ = test_app
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_positions"] == 0
    assert data["active_signals"] == 0


def test_overview_with_data(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    db.add(Position(market_id="m1", token_id="t1", side="YES", avg_entry_price=0.40, size=100, current_price=0.60, unrealized_pnl=20))
    db.add(Signal(market_id="m1", type="ARBITRAGE", current_price=0.50, edge_pct=3.0, confidence=90, status="NEW"))
    db.commit()
    resp = client.get("/api/overview")
    data = resp.json()
    assert data["active_positions"] == 1
    assert data["active_signals"] == 1
    assert data["unrealized_pnl"] == 20.0
