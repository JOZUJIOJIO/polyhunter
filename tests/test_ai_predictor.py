import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings
from backend.db.models import Base, Market, Signal
from backend.signals.ai_predictor import AIPredictorDetector


@pytest.fixture
def ai_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_market(db, id="m1", question="Will X happen?", yes=0.50, no=0.50,
                 volume=10000, liquidity=5000, active=True, end_date=None):
    if end_date is None:
        end_date = datetime(2026, 12, 31, tzinfo=timezone.utc)
    m = Market(
        id=id, condition_id=f"c_{id}", token_id_yes=f"ty_{id}", token_id_no=f"tn_{id}",
        question=question, active=active,
        last_price_yes=yes, last_price_no=no,
        volume_24h=volume, liquidity=liquidity, end_date=end_date,
    )
    db.add(m)
    db.commit()
    return m


def _mock_openrouter(probability, confidence, reasoning):
    """Return a mock httpx.post that returns OpenRouter-style response."""
    response_json = {
        "choices": [{"message": {"content": json.dumps({
            "probability": probability, "confidence": confidence, "reasoning": reasoning
        })}}]
    }
    mock_response = httpx.Response(200, json=response_json, request=httpx.Request("POST", "https://openrouter.ai"))
    return mock_response


def _settings(**overrides):
    defaults = dict(OPENROUTER_API_KEY="test-key", AI_EDGE_THRESHOLD_PCT=10.0,
                    AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000, AI_REQUEST_DELAY_SECONDS=0)
    defaults.update(overrides)
    return Settings(**defaults)


def test_generates_signal_when_ai_disagrees(ai_db):
    _make_market(ai_db, yes=0.50, no=0.50, question="Will BTC hit 100K?")
    mock_resp = _mock_openrouter(0.75, 80, "Strong momentum")

    with patch("backend.signals.ai_predictor.httpx.post", return_value=mock_resp):
        detector = AIPredictorDetector(session=ai_db, settings=_settings())
        signals = detector.detect()

    assert len(signals) == 1
    s = signals[0]
    assert s.type == "AI_PREDICTION"
    assert s.edge_pct == 25.0
    assert s.fair_value == 0.75
    detail = json.loads(s.source_detail)
    assert detail["direction"] == "UNDERPRICED"
    assert detail["reasoning"] == "Strong momentum"


def test_overpriced_direction(ai_db):
    _make_market(ai_db, yes=0.55, no=0.45, question="Will Y happen?")
    mock_resp = _mock_openrouter(0.30, 70, "Unlikely to happen")

    with patch("backend.signals.ai_predictor.httpx.post", return_value=mock_resp):
        detector = AIPredictorDetector(session=ai_db, settings=_settings())
        signals = detector.detect()

    assert len(signals) == 1
    detail = json.loads(signals[0].source_detail)
    assert detail["direction"] == "OVERPRICED"


def test_no_signal_when_ai_agrees(ai_db):
    _make_market(ai_db, yes=0.50, no=0.50)
    mock_resp = _mock_openrouter(0.52, 60, "Close to market")

    with patch("backend.signals.ai_predictor.httpx.post", return_value=mock_resp):
        detector = AIPredictorDetector(session=ai_db, settings=_settings())
        signals = detector.detect()

    assert len(signals) == 0


def test_no_signal_when_low_volume(ai_db):
    _make_market(ai_db, volume=500, liquidity=5000)
    mock_resp = _mock_openrouter(0.90, 90, "Very likely")

    with patch("backend.signals.ai_predictor.httpx.post", return_value=mock_resp) as mock_post:
        detector = AIPredictorDetector(session=ai_db, settings=_settings(AI_MIN_VOLUME_24H=5000))
        signals = detector.detect()

    assert len(signals) == 0
    mock_post.assert_not_called()


def test_no_signal_when_low_liquidity(ai_db):
    _make_market(ai_db, volume=10000, liquidity=100)
    mock_resp = _mock_openrouter(0.90, 90, "Very likely")

    with patch("backend.signals.ai_predictor.httpx.post", return_value=mock_resp) as mock_post:
        detector = AIPredictorDetector(session=ai_db, settings=_settings(AI_MIN_LIQUIDITY=1000))
        signals = detector.detect()

    assert len(signals) == 0
    mock_post.assert_not_called()


def test_handles_malformed_ai_response(ai_db):
    _make_market(ai_db)
    bad_resp = httpx.Response(200, json={
        "choices": [{"message": {"content": "I cannot answer this question clearly."}}]
    }, request=httpx.Request("POST", "https://openrouter.ai"))

    with patch("backend.signals.ai_predictor.httpx.post", return_value=bad_resp):
        detector = AIPredictorDetector(session=ai_db, settings=_settings())
        signals = detector.detect()

    assert len(signals) == 0


def test_handles_api_error(ai_db):
    _make_market(ai_db)

    with patch("backend.signals.ai_predictor.httpx.post", side_effect=Exception("API rate limit")):
        detector = AIPredictorDetector(session=ai_db, settings=_settings())
        signals = detector.detect()

    assert len(signals) == 0


def test_confidence_capped_at_85(ai_db):
    _make_market(ai_db, yes=0.50, no=0.50)
    mock_resp = _mock_openrouter(0.80, 99, "Extremely confident")

    with patch("backend.signals.ai_predictor.httpx.post", return_value=mock_resp):
        detector = AIPredictorDetector(session=ai_db, settings=_settings())
        signals = detector.detect()

    assert len(signals) == 1
    assert signals[0].confidence == 85


def test_max_markets_limit(ai_db):
    for i in range(30):
        _make_market(ai_db, id=f"m{i}", question=f"Q{i}?", volume=10000, liquidity=5000)
    mock_resp = _mock_openrouter(0.80, 70, "Likely")

    with patch("backend.signals.ai_predictor.httpx.post", return_value=mock_resp) as mock_post:
        detector = AIPredictorDetector(session=ai_db, settings=_settings(AI_MAX_MARKETS_PER_RUN=5))
        signals = detector.detect()

    assert mock_post.call_count == 5


def test_saves_signals(ai_db):
    _make_market(ai_db, yes=0.40, no=0.60)
    mock_resp = _mock_openrouter(0.75, 80, "Strong signal")

    with patch("backend.signals.ai_predictor.httpx.post", return_value=mock_resp):
        detector = AIPredictorDetector(session=ai_db, settings=_settings())
        signals = detector.detect()
        count = detector.save_signals(signals)

    assert count == 1
    saved = ai_db.query(Signal).first()
    assert saved.type == "AI_PREDICTION"
    assert saved.status == "NEW"
