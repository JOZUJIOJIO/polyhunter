# Bitget Integration Design — PolyHunter v0.2

## Goal

Extend PolyHunter to support Bitget exchange alongside Polymarket. Add real-time
price monitoring via WebSocket, strict rule-based trading execution, and Telegram
notifications for all trading events.

## Architecture: Exchange Adapter Pattern

```
                  ┌─────────────────┐
                  │  Signal Engine   │
                  │  (策略层)         │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Risk Manager   │
                  │  (风控层)         │
                  └────────┬────────┘
                           │
              ┌────────────▼────────────┐
              │   ExchangeAdapter ABC   │
              │   (统一交易所接口)        │
              └──────┬──────────┬───────┘
                     │          │
          ┌──────────▼──┐  ┌───▼──────────┐
          │ Polymarket  │  │   Bitget     │
          │  Adapter    │  │   Adapter    │
          └─────────────┘  └──────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
               REST API    WebSocket   Notifications
              (下单/查询)  (实时行情)    (Telegram)
```

## Components

### 1. ExchangeAdapter ABC (`backend/exchanges/base.py`)

```python
class ExchangeAdapter(ABC):
    async def get_ticker(symbol: str) -> Ticker
    async def get_orderbook(symbol: str, depth: int) -> OrderBook
    async def place_order(order: OrderRequest) -> OrderResult
    async def cancel_order(order_id: str) -> bool
    async def get_balance() -> dict[str, Decimal]
    async def get_positions() -> list[Position]
    async def subscribe_price(symbol: str, callback) -> None
    async def unsubscribe_price(symbol: str) -> None
```

### 2. Bitget Client (`backend/exchanges/bitget/`)

- `client.py` — REST API client (httpx + HMAC-SHA256 signing)
- `websocket.py` — WebSocket client for real-time price feeds
- `adapter.py` — ExchangeAdapter implementation for Bitget
- `models.py` — Bitget-specific data models

**Bitget API Authentication:**
- API Key + Secret Key + Passphrase
- HMAC-SHA256 signature on each request
- Timestamp-based request signing

**Supported Operations:**
- Spot trading (market/limit orders)
- USDT-M futures trading (market/limit orders)
- Account balance queries
- Position queries
- Real-time ticker/kline/orderbook via WebSocket

### 3. Polymarket Adapter (`backend/exchanges/polymarket/adapter.py`)

Wrap existing `executor.py` and `gamma_client.py` into ExchangeAdapter interface.

### 4. Real-Time Price Monitor (`backend/monitor/price_monitor.py`)

- WebSocket-based price feed for Bitget symbols
- Configurable monitoring intervals
- Technical indicator calculation (EMA, RSI, MACD, Bollinger Bands)
- Price alert thresholds
- Feeds data to signal detectors

### 5. Bitget Trading Strategies (`backend/signals/bitget_strategies.py`)

**Strategy 1: EMA Crossover**
- Fast EMA (9) crosses above Slow EMA (21) → BUY signal
- Fast EMA crosses below Slow EMA → SELL signal
- Confirm with RSI (not overbought/oversold)

**Strategy 2: Bollinger Band Breakout**
- Price breaks above upper band with volume surge → BUY
- Price breaks below lower band with volume surge → SELL
- Mean reversion variant: price touches band → counter-trade

**Strategy 3: RSI Divergence**
- Price makes new high but RSI doesn't → bearish divergence → SELL
- Price makes new low but RSI doesn't → bullish divergence → BUY

**Strategy 4: Grid Trading**
- Set price grid with configurable intervals
- Buy at each grid level below current price
- Sell at each grid level above current price
- Auto-rebalance on price movement

### 6. Telegram Notification System (`backend/notify/telegram.py`)

**Events to notify:**
- Signal detected (with details)
- Order placed / filled / cancelled
- Position opened / closed (with PnL)
- Circuit breaker triggered
- Daily PnL summary
- Price alerts triggered
- System errors

**Format:** Structured messages with emoji indicators:
- 🟢 BUY signal / order filled
- 🔴 SELL signal / order filled  
- ⚠️ Risk warning / circuit breaker
- 📊 Daily summary
- 🚨 System error

### 7. Configuration Additions

```python
# Bitget
BITGET_API_KEY = ""
BITGET_SECRET_KEY = ""
BITGET_PASSPHRASE = ""
BITGET_ACCOUNT_TYPE = "spot"  # spot | futures

# Bitget Trading
BITGET_SYMBOLS = "BTCUSDT,ETHUSDT"
BITGET_DEFAULT_SIZE_USD = 10.0
BITGET_MAX_POSITION_USD = 100.0
BITGET_LEVERAGE = 1  # 1 = no leverage (spot-like)

# Price Monitor
MONITOR_INTERVAL_SECONDS = 1
MONITOR_ALERT_CHANGE_PCT = 2.0

# Strategies
STRATEGY_EMA_FAST = 9
STRATEGY_EMA_SLOW = 21
STRATEGY_RSI_PERIOD = 14
STRATEGY_RSI_OVERBOUGHT = 70
STRATEGY_RSI_OVERSOLD = 30
STRATEGY_BB_PERIOD = 20
STRATEGY_BB_STD = 2.0
```

### 8. Database Additions

```python
# New table: BitgetTrade
BitgetTrade:
    id, symbol, side, order_type, price, size,
    status, order_id, strategy, pnl, created_at

# New table: PriceCandle  
PriceCandle:
    id, exchange, symbol, interval, open, high, low, close,
    volume, timestamp

# New table: Alert
Alert:
    id, exchange, symbol, type, message, acknowledged, created_at
```

### 9. API Routes

```
GET  /api/bitget/balance      — Account balance
GET  /api/bitget/positions    — Open positions
GET  /api/bitget/trades       — Trade history
POST /api/bitget/order        — Place order
GET  /api/bitget/ticker/:sym  — Current price
GET  /api/monitor/status      — Monitor status
POST /api/monitor/start       — Start price monitor
POST /api/monitor/stop        — Stop price monitor
GET  /api/alerts              — Price alerts
```

### 10. Scripts

```
scripts/bitget_trader.py      — Main Bitget auto-trader
scripts/price_monitor.py      — Standalone price monitor
scripts/bitget_grid.py        — Grid trading bot
```

## File Structure (New)

```
backend/
├── exchanges/
│   ├── __init__.py
│   ├── base.py              # ExchangeAdapter ABC
│   ├── polymarket/
│   │   ├── __init__.py
│   │   └── adapter.py       # Wrap existing code
│   └── bitget/
│       ├── __init__.py
│       ├── client.py         # REST API
│       ├── websocket.py      # WebSocket feeds
│       ├── adapter.py        # ExchangeAdapter impl
│       └── models.py         # Data models
├── monitor/
│   ├── __init__.py
│   ├── price_monitor.py      # Real-time monitor
│   └── indicators.py         # Technical indicators
├── notify/
│   ├── __init__.py
│   └── telegram.py           # Telegram notifications
├── signals/
│   └── bitget_strategies.py  # Bitget-specific strategies
```

## Risk Management Extensions

- Per-exchange position limits
- Per-symbol position limits
- Cross-exchange total exposure limit
- Bitget-specific: leverage controls, liquidation price monitoring
- Shared circuit breaker across all exchanges

## Non-Goals

- No margin trading beyond configurable leverage
- No options trading
- No cross-exchange arbitrage (Phase 3)
- No frontend changes in this iteration (API-first)
