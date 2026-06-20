"""Real-time price monitor with alert system."""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from backend.config import Settings
from backend.exchanges.base import ExchangeAdapter
from backend.monitor.indicators import compute_all, IndicatorResult
from backend.notify.telegram import TelegramNotifier

logger = logging.getLogger(__name__)


@dataclass
class PriceState:
    symbol: str
    prices: list[float] = field(default_factory=list)
    last_price: float = 0.0
    last_alert_time: float = 0.0
    base_price: float = 0.0  # Price at subscription start
    high_since_start: float = 0.0
    low_since_start: float = float("inf")


class PriceMonitor:
    """Real-time price monitoring with alerts and indicator tracking."""

    def __init__(
        self,
        exchange: ExchangeAdapter,
        notifier: TelegramNotifier | None = None,
        settings: Settings | None = None,
    ):
        self.exchange = exchange
        self.notifier = notifier
        self.settings = settings or Settings()
        self._states: dict[str, PriceState] = {}
        self._running = False
        self._alert_cooldown = 300  # 5 minutes between alerts for same symbol
        self._price_callbacks: dict[str, list] = defaultdict(list)
        self._kline_history: dict[str, list[float]] = defaultdict(list)
        self._max_history = 200  # Max candles to keep

    async def start(self, symbols: list[str]) -> None:
        self._running = True
        logger.info(f"Starting price monitor for {symbols}")

        for symbol in symbols:
            self._states[symbol] = PriceState(symbol=symbol)
            await self.exchange.subscribe_price(symbol, self._on_price_update)

            # Fetch initial klines for indicator calculation
            try:
                klines = await self.exchange.get_klines(symbol, interval="5m", limit=self._max_history)
                self._kline_history[symbol] = [k.close for k in klines]
                if klines:
                    self._states[symbol].base_price = klines[-1].close
                    self._states[symbol].last_price = klines[-1].close
            except Exception as e:
                logger.error(f"Failed to fetch initial klines for {symbol}: {e}")

        logger.info(f"Price monitor started for {len(symbols)} symbols")

    async def stop(self) -> None:
        self._running = False
        for symbol in list(self._states.keys()):
            try:
                await self.exchange.unsubscribe_price(symbol)
            except Exception:
                pass
        self._states.clear()
        logger.info("Price monitor stopped")

    def add_callback(self, symbol: str, callback) -> None:
        self._price_callbacks[symbol].append(callback)

    def get_state(self, symbol: str) -> PriceState | None:
        return self._states.get(symbol)

    def get_indicators(self, symbol: str) -> IndicatorResult | None:
        prices = self._kline_history.get(symbol, [])
        if len(prices) < 26:  # Need at least enough for MACD
            return None
        return compute_all(
            prices,
            ema_fast_period=self.settings.STRATEGY_EMA_FAST,
            ema_slow_period=self.settings.STRATEGY_EMA_SLOW,
            rsi_period=self.settings.STRATEGY_RSI_PERIOD,
            bb_period=self.settings.STRATEGY_BB_PERIOD,
            bb_std=self.settings.STRATEGY_BB_STD,
        )

    async def _on_price_update(self, symbol: str, price: float, timestamp: float) -> None:
        state = self._states.get(symbol)
        if not state:
            return

        old_price = state.last_price
        state.last_price = price
        state.prices.append(price)

        # Keep price history bounded
        if len(state.prices) > 1000:
            state.prices = state.prices[-500:]

        # Update high/low
        if price > state.high_since_start:
            state.high_since_start = price
        if price < state.low_since_start:
            state.low_since_start = price

        # Update kline history
        self._kline_history[symbol].append(price)
        if len(self._kline_history[symbol]) > self._max_history:
            self._kline_history[symbol] = self._kline_history[symbol][-self._max_history:]

        # Check for price alerts
        if state.base_price > 0 and old_price > 0:
            change_pct = (price - state.base_price) / state.base_price * 100
            alert_threshold = self.settings.MONITOR_ALERT_CHANGE_PCT

            now = time.time()
            if abs(change_pct) >= alert_threshold and (now - state.last_alert_time) > self._alert_cooldown:
                state.last_alert_time = now
                alert_type = "SURGE" if change_pct > 0 else "DROP"
                logger.info(f"Price alert: {symbol} {alert_type} {change_pct:+.2f}% → ${price:,.2f}")

                if self.notifier:
                    await self.notifier.notify_price_alert(
                        exchange=self.exchange.name,
                        symbol=symbol,
                        price=price,
                        change_pct=change_pct,
                        alert_type=alert_type,
                    )

        # Call registered callbacks
        for cb in self._price_callbacks.get(symbol, []):
            try:
                result = cb(symbol, price, timestamp)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Price callback error for {symbol}: {e}")

    @property
    def monitored_symbols(self) -> list[str]:
        return list(self._states.keys())

    @property
    def is_running(self) -> bool:
        return self._running
