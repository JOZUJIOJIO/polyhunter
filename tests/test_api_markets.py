from backend.db.models import Market


def test_list_markets(test_app):
    client, db = test_app
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True, last_price_yes=0.50, last_price_no=0.50,
        volume_24h=10000, category="politics",
    )
    db.add(market)
    db.commit()
    resp = client.get("/api/markets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "m1"


def test_list_markets_filter_active(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Active?", active=True))
    db.add(Market(id="m2", condition_id="c2", token_id_yes="t3", token_id_no="t4", question="Closed?", active=False))
    db.commit()
    resp = client.get("/api/markets?active=true")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_market_not_found(test_app):
    client, _ = test_app
    resp = client.get("/api/markets/nonexistent")
    assert resp.status_code == 404
