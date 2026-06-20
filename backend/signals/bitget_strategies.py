"""Trading strategies for Bitget exchange."""

import logging
from dataclasses import dataclass
from enum import Enum

from backend.config import Settings
from backend.monitor.indicators import IndicatorResult

logger = logging.getLogger(__name__)


class StrategySignalType(str, Enum):
    EMA_CROSSOVER = "EMA_CROSSOVER"
    BOLLINGER_BREAKOUT = "BOLLINGER_BREAKOUT"
    RSI_DIVERGENCE = "RSI_DIVERGENCE"
    MACD_CROSSOVER = "MACD_CROSSOVER"


@dataclass
class StrategySignal:
    symbol: str
    strategy: StrategySignalType
    side: str  # "BUY" or "SELL"
    price: float
    confidence: int  # 0-100
    edge_pct: float
    reason: str


class BitgetStrategyEngine:
    """Evaluates trading strategies against current market indicators."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def evaluate(self, symbol: str, price: float, indicators: IndicatorResult) -> list[StrategySignal]:
        signals = []

        ema_signal = self._check_ema_crossover(symbol, price, indicators)
        if ema_signal:
            signals.append(ema_signal)

        bb_signal = self._check_bollinger_breakout(symbol, price, indicators)
        if bb_signal:
            signals.append(bb_signal)

        rsi_signal = self._check_rsi_extremes(symbol, price, indicators)
        if rsi_signal:
            signals.append(rsi_signal)

        macd_signal = self._check_macd_crossover(symbol, price, indicators)
        if macd_signal:
            signals.append(macd_signal)

        return signals

    def _check_ema_crossover(
        self, symbol: str, price: float, ind: IndicatorResult
    ) -> StrategySignal | None:
        """EMA fast/slow crossover strategy."""
        if len(ind.ema_fast) < 3 or len(ind.ema_slow) < 3:
            return None

        fast_prev = ind.ema_fast[-2]
        fast_curr = ind.ema_fast[-1]
        slow_prev = ind.ema_slow[-2]
        slow_curr = ind.ema_slow[-1]

        # Skip if values are zero (not enough data)
        if fast_prev == 0 or slow_prev == 0:
            return None

        rsi_val = ind.rsi[-1] if ind.rsi else 50

        # Bullish crossover: fast crosses above slow
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            if rsi_val < self.settings.STRATEGY_RSI_OVERBOUGHT:
                edge = (fast_curr - slow_curr) / slow_curr * 100
                return StrategySignal(
                    symbol=symbol,
                    strategy=StrategySignalType.EMA_CROSSOVER,
                    side="BUY",
                    price=price,
                    confidence=min(80, int(50 + edge * 5)),
                    edge_pct=edge,
                    reason=f"EMA{self.settings.STRATEGY_EMA_FAST} crossed above EMA{self.settings.STRATEGY_EMA_SLOW}, RSI={rsi_val:.0f}",
                )

        # Bearish crossover: fast crosses below slow
        if fast_prev >= slow_prev and fast_curr < slow_curr:
            if rsi_val > self.settings.STRATEGY_RSI_OVERSOLD:
                edge = (slow_curr - fast_curr) / slow_curr * 100
                return StrategySignal(
                    symbol=symbol,
                    strategy=StrategySignalType.EMA_CROSSOVER,
                    side="SELL",
                    price=price,
                    confidence=min(80, int(50 + edge * 5)),
                    edge_pct=edge,
                    reason=f"EMA{self.settings.STRATEGY_EMA_FAST} crossed below EMA{self.settings.STRATEGY_EMA_SLOW}, RSI={rsi_val:.0f}",
                )

        return None

    def _check_bollinger_breakout(
        self, symbol: str, price: float, ind: IndicatorResult
    ) -> StrategySignal | None:
        """Bollinger Band breakout/mean-reversion strategy."""
        if len(ind.bb_upper) < 2 or ind.bb_upper[-1] == 0:
            return None

        upper = ind.bb_upper[-1]
        lower = ind.bb_lower[-1]
        middle = ind.bb_middle[-1]

        if upper == lower:
            return None

        # Mean reversion: price below lower band → BUY (expect reversion to mean)
        if price <= lower:
            distance_pct = (lower - price) / middle * 100
            return StrategySignal(
                symbol=symbol,
                strategy=StrategySignalType.BOLLINGER_BREAKOUT,
                side="BUY",
                price=price,
                confidence=min(75, int(50 + distance_pct * 3)),
                edge_pct=distance_pct,
                reason=f"Price ${price:,.2f} below lower BB ${lower:,.2f}, mean reversion expected",
            )

        # Mean reversion: price above upper band → SELL
        if price >= upper:
            distance_pct = (price - upper) / middle * 100
            return StrategySignal(
                symbol=symbol,
                strategy=StrategySignalType.BOLLINGER_BREAKOUT,
                side="SELL",
                price=price,
                confidence=min(75, int(50 + distance_pct * 3)),
                edge_pct=distance_pct,
                reason=f"Price ${price:,.2f} above upper BB ${upper:,.2f}, mean reversion expected",
            )

        return None

    def _check_rsi_extremes(
        self, symbol: str, price: float, ind: IndicatorResult
    ) -> StrategySignal | None:
        """RSI overbought/oversold strategy."""
        if len(ind.rsi) < 3:
            return None

        rsi_val = ind.rsi[-1]
        rsi_prev = ind.rsi[-2]

        # Oversold bounce: RSI was below oversold, now rising
        if rsi_prev < self.settings.STRATEGY_RSI_OVERSOLD and rsi_val > rsi_prev:
            edge = (self.settings.STRATEGY_RSI_OVERSOLD - rsi_val) / 100 * 10
            return StrategySignal(
                symbol=symbol,
                strategy=StrategySignalType.RSI_DIVERGENCE,
                side="BUY",
                price=price,
                confidence=min(70, int(40 + abs(edge) * 5)),
                edge_pct=abs(edge),
                reason=f"RSI oversold bounce: {rsi_prev:.0f} → {rsi_val:.0f}",
            )

        # Overbought reversal: RSI was above overbought, now falling
        if rsi_prev > self.settings.STRATEGY_RSI_OVERBOUGHT and rsi_val < rsi_prev:
            edge = (rsi_val - self.settings.STRATEGY_RSI_OVERBOUGHT) / 100 * 10
            return StrategySignal(
                symbol=symbol,
                strategy=StrategySignalType.RSI_DIVERGENCE,
                side="SELL",
                price=price,
                confidence=min(70, int(40 + abs(edge) * 5)),
                edge_pct=abs(edge),
                reason=f"RSI overbought reversal: {rsi_prev:.0f} → {rsi_val:.0f}",
            )

        return None

    def _check_macd_crossover(
        self, symbol: str, price: float, ind: IndicatorResult
    ) -> StrategySignal | None:
        """MACD line/signal crossover strategy."""
        if len(ind.macd_line) < 3 or len(ind.macd_signal) < 3:
            return None

        macd_prev = ind.macd_line[-2]
        macd_curr = ind.macd_line[-1]
        sig_prev = ind.macd_signal[-2]
        sig_curr = ind.macd_signal[-1]

        if sig_prev == 0 or sig_curr == 0:
            return None

        # Bullish crossover: MACD crosses above signal
        if macd_prev <= sig_prev and macd_curr > sig_curr:
            hist = ind.macd_histogram[-1]
            edge = abs(hist) / price * 100 if price > 0 else 0
            return StrategySignal(
                symbol=symbol,
                strategy=StrategySignalType.MACD_CROSSOVER,
                side="BUY",
                price=price,
                confidence=min(70, int(45 + edge * 10)),
                edge_pct=edge,
                reason=f"MACD bullish crossover, histogram={hist:.4f}",
            )

        # Bearish crossover: MACD crosses below signal
        if macd_prev >= sig_prev and macd_curr < sig_curr:
            hist = ind.macd_histogram[-1]
            edge = abs(hist) / price * 100 if price > 0 else 0
            return StrategySignal(
                symbol=symbol,
                strategy=StrategySignalType.MACD_CROSSOVER,
                side="SELL",
                price=price,
                confidence=min(70, int(45 + edge * 10)),
                edge_pct=edge,
                reason=f"MACD bearish crossover, histogram={hist:.4f}",
            )

        return None
