"""Tests for Bitget trading strategies."""

import pytest
from backend.config import Settings
from backend.monitor.indicators import IndicatorResult
from backend.signals.bitget_strategies import BitgetStrategyEngine, StrategySignalType


def make_settings(**overrides):
    defaults = {
        "STRATEGY_EMA_FAST": 9,
        "STRATEGY_EMA_SLOW": 21,
        "STRATEGY_RSI_PERIOD": 14,
        "STRATEGY_RSI_OVERBOUGHT": 70,
        "STRATEGY_RSI_OVERSOLD": 30,
        "STRATEGY_BB_PERIOD": 20,
        "STRATEGY_BB_STD": 2.0,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestEMACrossover:
    def test_bullish_crossover(self):
        engine = BitgetStrategyEngine(make_settings())
        indicators = IndicatorResult(
            ema_fast=[0] * 8 + [99, 100, 101],  # crosses above
            ema_slow=[0] * 8 + [100, 100, 100],
            rsi=[50] * 11,
            macd_line=[0] * 11,
            macd_signal=[0] * 11,
            macd_histogram=[0] * 11,
            bb_upper=[0] * 11,
            bb_middle=[0] * 11,
            bb_lower=[0] * 11,
        )
        signals = engine.evaluate("BTCUSDT", 50000, indicators)
        ema_signals = [s for s in signals if s.strategy == StrategySignalType.EMA_CROSSOVER]
        assert len(ema_signals) == 1
        assert ema_signals[0].side == "BUY"

    def test_bearish_crossover(self):
        engine = BitgetStrategyEngine(make_settings())
        indicators = IndicatorResult(
            ema_fast=[0] * 8 + [101, 100, 99],  # crosses below
            ema_slow=[0] * 8 + [100, 100, 100],
            rsi=[50] * 11,
            macd_line=[0] * 11,
            macd_signal=[0] * 11,
            macd_histogram=[0] * 11,
            bb_upper=[0] * 11,
            bb_middle=[0] * 11,
            bb_lower=[0] * 11,
        )
        signals = engine.evaluate("BTCUSDT", 50000, indicators)
        ema_signals = [s for s in signals if s.strategy == StrategySignalType.EMA_CROSSOVER]
        assert len(ema_signals) == 1
        assert ema_signals[0].side == "SELL"

    def test_no_crossover(self):
        engine = BitgetStrategyEngine(make_settings())
        indicators = IndicatorResult(
            ema_fast=[0] * 8 + [105, 106, 107],  # always above, no cross
            ema_slow=[0] * 8 + [100, 100, 100],
            rsi=[50] * 11,
            macd_line=[0] * 11,
            macd_signal=[0] * 11,
            macd_histogram=[0] * 11,
            bb_upper=[0] * 11,
            bb_middle=[0] * 11,
            bb_lower=[0] * 11,
        )
        signals = engine.evaluate("BTCUSDT", 50000, indicators)
        ema_signals = [s for s in signals if s.strategy == StrategySignalType.EMA_CROSSOVER]
        assert len(ema_signals) == 0


class TestBollingerBreakout:
    def test_buy_below_lower_band(self):
        engine = BitgetStrategyEngine(make_settings())
        indicators = IndicatorResult(
            ema_fast=[0] * 3,
            ema_slow=[0] * 3,
            rsi=[50] * 3,
            macd_line=[0] * 3,
            macd_signal=[0] * 3,
            macd_histogram=[0] * 3,
            bb_upper=[110] * 3,
            bb_middle=[100] * 3,
            bb_lower=[90] * 3,
        )
        # Price below lower band
        signals = engine.evaluate("BTCUSDT", 88, indicators)
        bb_signals = [s for s in signals if s.strategy == StrategySignalType.BOLLINGER_BREAKOUT]
        assert len(bb_signals) == 1
        assert bb_signals[0].side == "BUY"

    def test_sell_above_upper_band(self):
        engine = BitgetStrategyEngine(make_settings())
        indicators = IndicatorResult(
            ema_fast=[0] * 3,
            ema_slow=[0] * 3,
            rsi=[50] * 3,
            macd_line=[0] * 3,
            macd_signal=[0] * 3,
            macd_histogram=[0] * 3,
            bb_upper=[110] * 3,
            bb_middle=[100] * 3,
            bb_lower=[90] * 3,
        )
        signals = engine.evaluate("BTCUSDT", 112, indicators)
        bb_signals = [s for s in signals if s.strategy == StrategySignalType.BOLLINGER_BREAKOUT]
        assert len(bb_signals) == 1
        assert bb_signals[0].side == "SELL"


class TestRSIExtremes:
    def test_oversold_bounce(self):
        engine = BitgetStrategyEngine(make_settings())
        indicators = IndicatorResult(
            ema_fast=[0] * 4,
            ema_slow=[0] * 4,
            rsi=[50, 40, 25, 28],  # was below 30, now rising
            macd_line=[0] * 4,
            macd_signal=[0] * 4,
            macd_histogram=[0] * 4,
            bb_upper=[0] * 4,
            bb_middle=[0] * 4,
            bb_lower=[0] * 4,
        )
        signals = engine.evaluate("BTCUSDT", 50000, indicators)
        rsi_signals = [s for s in signals if s.strategy == StrategySignalType.RSI_DIVERGENCE]
        assert len(rsi_signals) == 1
        assert rsi_signals[0].side == "BUY"

    def test_overbought_reversal(self):
        engine = BitgetStrategyEngine(make_settings())
        indicators = IndicatorResult(
            ema_fast=[0] * 4,
            ema_slow=[0] * 4,
            rsi=[50, 65, 75, 72],  # was above 70, now falling
            macd_line=[0] * 4,
            macd_signal=[0] * 4,
            macd_histogram=[0] * 4,
            bb_upper=[0] * 4,
            bb_middle=[0] * 4,
            bb_lower=[0] * 4,
        )
        signals = engine.evaluate("BTCUSDT", 50000, indicators)
        rsi_signals = [s for s in signals if s.strategy == StrategySignalType.RSI_DIVERGENCE]
        assert len(rsi_signals) == 1
        assert rsi_signals[0].side == "SELL"


class TestMACDCrossover:
    def test_bullish_macd(self):
        engine = BitgetStrategyEngine(make_settings())
        indicators = IndicatorResult(
            ema_fast=[0] * 4,
            ema_slow=[0] * 4,
            rsi=[50] * 4,
            macd_line=[0, -1, -0.5, 0.5],    # crosses above signal
            macd_signal=[0, -0.5, -0.3, 0.2],
            macd_histogram=[0, -0.5, -0.2, 0.3],
            bb_upper=[0] * 4,
            bb_middle=[0] * 4,
            bb_lower=[0] * 4,
        )
        signals = engine.evaluate("BTCUSDT", 50000, indicators)
        macd_signals = [s for s in signals if s.strategy == StrategySignalType.MACD_CROSSOVER]
        assert len(macd_signals) == 1
        assert macd_signals[0].side == "BUY"
