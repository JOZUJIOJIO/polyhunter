from backend.db.models import Market, Signal


def test_list_signals(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    db.add(Signal(market_id="m1", type="ARBITRAGE", current_price=0.50, edge_pct=3.0, confidence=90, status="NEW"))
    db.commit()
    resp = client.get("/api/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "ARBITRAGE"
    assert data[0]["market_question"] == "Q?"


def test_dismiss_signal(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    db.add(Signal(market_id="m1", type="ARBITRAGE", current_price=0.50, edge_pct=3.0, confidence=90, status="NEW"))
    db.commit()
    signal = db.query(Signal).first()
    resp = client.post(f"/api/signals/{signal.id}/dismiss")
    assert resp.status_code == 200
    db.refresh(signal)
    assert signal.status == "DISMISSED"
