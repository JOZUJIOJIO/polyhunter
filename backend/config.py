from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Polymarket credentials
    POLYMARKET_PRIVATE_KEY: str = ""
    POLYMARKET_API_KEY: str = ""
    POLYMARKET_API_SECRET: str = ""
    POLYMARKET_API_PASSPHRASE: str = ""
    POLYMARKET_FUNDER: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./polyhunter.db"

    # Risk management
    RISK_MAX_SINGLE_BET_PCT: int = 10
    RISK_MAX_DAILY_LOSS_PCT: int = 5
    RISK_MAX_POSITION_PCT: int = 20
    RISK_MIN_EDGE_PCT: float = 1.0
    RISK_MAX_POSITIONS: int = 10
    RISK_EXPIRY_BUFFER_HOURS: int = 24

    # Polymarket fee (used in edge calculations)
    POLYMARKET_FEE_PCT: float = 2.0

    # Telegram (optional)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Phase 2: AI
    ANTHROPIC_API_KEY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
