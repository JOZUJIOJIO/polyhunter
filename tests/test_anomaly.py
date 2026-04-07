import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Market, Signal
from backend.signals.anomaly import AnomalyDetector


@pytest.fixture
def anomaly_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def make_price_history(mean: float, count: int = 50, std: float = 0.02) -> list[dict]:
    """Generate synthetic price history around a mean."""
    import random
    random.seed(42)
    return [
        {"t": i, "p": round(mean + random.gauss(0, std), 4)}
        for i in range(count)
    ]


def test_detects_price_spike(anomaly_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.85,  # way above mean of ~0.50
        last_price_no=0.15,
        volume_24h=100000,
    )
    anomaly_db.add(market)
    anomaly_db.commit()

    history = make_price_history(mean=0.50, count=50, std=0.02)
    detector = AnomalyDetector(session=anomaly_db, sigma_threshold=2.0, min_volume=1000)
    signals = detector.detect(price_histories={"m1": history})

    assert len(signals) == 1
    s = signals[0]
    assert s.type == "PRICE_ANOMALY"
    assert s.market_id == "m1"
    detail = json.loads(s.source_detail)
    assert "z_score" in detail
    assert abs(detail["z_score"]) > 2.0


def test_no_signal_when_price_normal(anomaly_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.51,  # very close to mean
        last_price_no=0.49,
        volume_24h=100000,
    )
    anomaly_db.add(market)
    anomaly_db.commit()

    history = make_price_history(mean=0.50, count=50, std=0.02)
    detector = AnomalyDetector(session=anomaly_db, sigma_threshold=2.0, min_volume=1000)
    signals = detector.detect(price_histories={"m1": history})

    assert len(signals) == 0


def test_no_signal_when_low_volume(anomaly_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.85,
        last_price_no=0.15,
        volume_24h=500,  # below min_volume threshold
    )
    anomaly_db.add(market)
    anomaly_db.commit()

    history = make_price_history(mean=0.50, count=50, std=0.02)
    detector = AnomalyDetector(session=anomaly_db, sigma_threshold=2.0, min_volume=1000)
    signals = detector.detect(price_histories={"m1": history})

    assert len(signals) == 0


def test_no_signal_when_insufficient_history(anomaly_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.85, last_price_no=0.15,
        volume_24h=100000,
    )
    anomaly_db.add(market)
    anomaly_db.commit()

    history = make_price_history(mean=0.50, count=3, std=0.02)  # too few
    detector = AnomalyDetector(session=anomaly_db, sigma_threshold=2.0, min_volume=1000)
    signals = detector.detect(price_histories={"m1": history})

    assert len(signals) == 0
