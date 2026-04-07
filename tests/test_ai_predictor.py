import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

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


def _mock_claude_response(probability, confidence, reasoning):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text=json.dumps({"probability": probability, "confidence": confidence, "reasoning": reasoning})
    )]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_generates_signal_when_ai_disagrees(ai_db):
    _make_market(ai_db, yes=0.50, no=0.50, question="Will BTC hit 100K?")
    mock_client = _mock_claude_response(0.75, 80, "Strong momentum")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_EDGE_THRESHOLD_PCT=10.0,
                        AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert len(signals) == 1
    s = signals[0]
    assert s.type == "AI_PREDICTION"
    assert s.edge_pct == 25.0  # |0.75 - 0.50| * 100
    assert s.fair_value == 0.75
    detail = json.loads(s.source_detail)
    assert detail["direction"] == "UNDERPRICED"
    assert detail["reasoning"] == "Strong momentum"


def test_overpriced_direction(ai_db):
    _make_market(ai_db, yes=0.55, no=0.45, question="Will Y happen?")
    mock_client = _mock_claude_response(0.30, 70, "Unlikely to happen")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_EDGE_THRESHOLD_PCT=10.0,
                        AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert len(signals) == 1
    detail = json.loads(signals[0].source_detail)
    assert detail["direction"] == "OVERPRICED"


def test_no_signal_when_ai_agrees(ai_db):
    _make_market(ai_db, yes=0.50, no=0.50)
    mock_client = _mock_claude_response(0.52, 60, "Close to market")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_EDGE_THRESHOLD_PCT=10.0,
                        AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert len(signals) == 0


def test_no_signal_when_low_volume(ai_db):
    _make_market(ai_db, volume=500, liquidity=5000)  # Below AI_MIN_VOLUME_24H
    mock_client = _mock_claude_response(0.90, 90, "Very likely")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_MIN_VOLUME_24H=5000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert len(signals) == 0
    mock_client.messages.create.assert_not_called()


def test_no_signal_when_low_liquidity(ai_db):
    _make_market(ai_db, volume=10000, liquidity=100)  # Below AI_MIN_LIQUIDITY
    mock_client = _mock_claude_response(0.90, 90, "Very likely")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert len(signals) == 0
    mock_client.messages.create.assert_not_called()


def test_handles_malformed_ai_response(ai_db):
    _make_market(ai_db)
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="I cannot answer this question clearly.")]
    mock_client.messages.create.return_value = mock_response
    settings = Settings(ANTHROPIC_API_KEY="test", AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert len(signals) == 0  # Graceful degradation, no crash


def test_handles_api_error(ai_db):
    _make_market(ai_db)
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API rate limit exceeded")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert len(signals) == 0  # No crash


def test_confidence_capped_at_85(ai_db):
    _make_market(ai_db, yes=0.50, no=0.50)
    mock_client = _mock_claude_response(0.80, 99, "Extremely confident")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_EDGE_THRESHOLD_PCT=10.0,
                        AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert len(signals) == 1
    assert signals[0].confidence == 85  # Capped


def test_max_markets_limit(ai_db):
    for i in range(30):
        _make_market(ai_db, id=f"m{i}", question=f"Q{i}?", volume=10000, liquidity=5000)
    mock_client = _mock_claude_response(0.80, 70, "Likely")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_EDGE_THRESHOLD_PCT=10.0,
                        AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000,
                        AI_MAX_MARKETS_PER_RUN=5, AI_REQUEST_DELAY_SECONDS=0)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()

    assert mock_client.messages.create.call_count == 5  # Only 5 API calls


def test_saves_signals(ai_db):
    _make_market(ai_db, yes=0.40, no=0.60)
    mock_client = _mock_claude_response(0.75, 80, "Strong signal")
    settings = Settings(ANTHROPIC_API_KEY="test", AI_EDGE_THRESHOLD_PCT=10.0,
                        AI_MIN_VOLUME_24H=1000, AI_MIN_LIQUIDITY=1000)

    with patch("backend.signals.ai_predictor.anthropic.Anthropic", return_value=mock_client):
        detector = AIPredictorDetector(session=ai_db, settings=settings)
        signals = detector.detect()
        count = detector.save_signals(signals)

    assert count == 1
    saved = ai_db.query(Signal).first()
    assert saved.type == "AI_PREDICTION"
    assert saved.status == "NEW"
