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

    # Bitget
    BITGET_API_KEY: str = ""
    BITGET_SECRET_KEY: str = ""
    BITGET_PASSPHRASE: str = ""
    BITGET_ACCOUNT_TYPE: str = "spot"  # "spot" or "futures"
    BITGET_SYMBOLS: str = "BTCUSDT,ETHUSDT"  # comma-separated
    BITGET_DEFAULT_SIZE_USD: float = 5.0
    BITGET_MAX_POSITION_USD: float = 100.0
    BITGET_LEVERAGE: int = 1  # 1 = no leverage

    # Bitget auto-trade
    BITGET_AUTO_TRADE_ENABLED: bool = False
    BITGET_MIN_CONFIDENCE: int = 60
    BITGET_MIN_EDGE_PCT: float = 0.5
    BITGET_STOP_LOSS_PCT: float = 5.0    # 亏损超过 5% 止损
    BITGET_TAKE_PROFIT_PCT: float = 10.0  # 盈利超过 10% 止盈

    # Price monitor
    MONITOR_INTERVAL_SECONDS: int = 1
    MONITOR_ALERT_CHANGE_PCT: float = 2.0

    # Strategies
    STRATEGY_EMA_FAST: int = 9
    STRATEGY_EMA_SLOW: int = 21
    STRATEGY_RSI_PERIOD: int = 14
    STRATEGY_RSI_OVERBOUGHT: int = 70
    STRATEGY_RSI_OVERSOLD: int = 30
    STRATEGY_BB_PERIOD: int = 20
    STRATEGY_BB_STD: float = 2.0

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

    # Circuit breaker
    CIRCUIT_BREAKER_CONSECUTIVE_LOSSES: int = 5  # N 笔连亏后熔断
    CIRCUIT_BREAKER_COOLDOWN_MINUTES: int = 60   # 熔断冷却时间

    # BTC 5-minute trading
    BTC_5M_ENABLED: bool = False
    BTC_5M_BET_SIZE_USD: float = 5.0
    BTC_5M_MIN_EDGE_PCT: float = 5.0
    BTC_5M_ENTRY_SECONDS_BEFORE_END: int = 60
    BTC_5M_SIMULATIONS: int = 1000
    PROXY_URL: str = "http://127.0.0.1:7897"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
