import os
from backend.config import Settings


def test_settings_defaults():
    settings = Settings(
        POLYMARKET_PRIVATE_KEY="0xtest",
        POLYMARKET_API_KEY="test_key",
        POLYMARKET_API_SECRET="test_secret",
    )
    assert settings.DATABASE_URL == "sqlite:///./polyhunter.db"
    assert settings.RISK_MAX_SINGLE_BET_PCT == 10
    assert settings.RISK_MAX_DAILY_LOSS_PCT == 5
    assert settings.RISK_MAX_POSITION_PCT == 20
    assert settings.RISK_MIN_EDGE_PCT == 1.0
    assert settings.RISK_MAX_POSITIONS == 10
    assert settings.RISK_EXPIRY_BUFFER_HOURS == 24
    assert settings.POLYMARKET_FEE_PCT == 2.0


def test_settings_custom_values():
    settings = Settings(
        POLYMARKET_PRIVATE_KEY="0xtest",
        POLYMARKET_API_KEY="key",
        POLYMARKET_API_SECRET="secret",
        RISK_MAX_SINGLE_BET_PCT=5,
        RISK_MIN_EDGE_PCT=2.5,
    )
    assert settings.RISK_MAX_SINGLE_BET_PCT == 5
    assert settings.RISK_MIN_EDGE_PCT == 2.5
