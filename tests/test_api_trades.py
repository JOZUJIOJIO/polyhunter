from backend.db.models import Market, Trade


def test_list_trades(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    db.add(Trade(market_id="m1", token_id="t1", side="BUY", price=0.50, size=100, cost=50, status="FILLED"))
    db.commit()
    resp = client.get("/api/trades")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_trade(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    resp = client.post("/api/trades", json={
        "market_id": "m1", "token_id": "t1", "side": "BUY", "price": 0.50, "size": 100,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["cost"] == 50.0
