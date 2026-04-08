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

    # Phase 2: AI (via OpenRouter)
    OPENROUTER_API_KEY: str = ""
    AI_MODEL: str = "anthropic/claude-sonnet-4"
    AI_EDGE_THRESHOLD_PCT: float = 10.0
    AI_MIN_VOLUME_24H: float = 5000.0
    AI_MIN_LIQUIDITY: float = 1000.0
    AI_MAX_MARKETS_PER_RUN: int = 20
    AI_REQUEST_DELAY_SECONDS: float = 1.0

    # Auto-trade settings
    AUTO_TRADE_ENABLED: bool = False
    AUTO_TRADE_MIN_CONFIDENCE: int = 70
    AUTO_TRADE_MIN_EDGE_PCT: float = 5.0
    AUTO_TRADE_SIZE_USD: float = 5.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
