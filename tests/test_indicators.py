"""Tests for technical analysis indicators."""

import pytest
from backend.monitor.indicators import ema, sma, rsi, macd, bollinger_bands, compute_all


class TestEMA:
    def test_basic_ema(self):
        prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        result = ema(prices, 5)
        assert len(result) == len(prices)
        assert result[4] == pytest.approx(12.0, abs=0.01)  # SMA of first 5
        assert result[-1] > result[-2]  # Uptrend

    def test_ema_insufficient_data(self):
        prices = [10, 11, 12]
        result = ema(prices, 5)
        assert all(v == 0.0 for v in result)

    def test_ema_flat_prices(self):
        prices = [100.0] * 20
        result = ema(prices, 10)
        # After enough data, EMA should converge to the constant price
        assert result[-1] == pytest.approx(100.0, abs=0.01)


class TestSMA:
    def test_basic_sma(self):
        prices = [1, 2, 3, 4, 5]
        result = sma(prices, 3)
        assert result[2] == pytest.approx(2.0)  # (1+2+3)/3
        assert result[3] == pytest.approx(3.0)  # (2+3+4)/3
        assert result[4] == pytest.approx(4.0)  # (3+4+5)/3


class TestRSI:
    def test_strong_uptrend(self):
        # Monotonically increasing → RSI should be near 100
        prices = list(range(1, 30))
        result = rsi(prices, 14)
        assert result[-1] > 90

    def test_strong_downtrend(self):
        prices = list(range(30, 1, -1))
        result = rsi(prices, 14)
        assert result[-1] < 10

    def test_insufficient_data(self):
        prices = [10, 11, 12]
        result = rsi(prices, 14)
        assert all(v == 50.0 for v in result)


class TestMACD:
    def test_macd_shape(self):
        prices = list(range(1, 50))
        macd_line, signal_line, histogram = macd(prices)
        assert len(macd_line) == len(prices)
        assert len(signal_line) == len(prices)
        assert len(histogram) == len(prices)


class TestBollingerBands:
    def test_bands_shape(self):
        prices = [100 + i * 0.5 for i in range(30)]
        upper, middle, lower = bollinger_bands(prices, 20, 2.0)
        assert len(upper) == len(prices)
        # After period, bands should be computed
        assert upper[-1] > middle[-1] > lower[-1]

    def test_flat_prices_narrow_bands(self):
        prices = [100.0] * 30
        upper, middle, lower = bollinger_bands(prices, 20, 2.0)
        # Flat prices → zero std → bands collapse to middle
        assert upper[-1] == pytest.approx(100.0)
        assert lower[-1] == pytest.approx(100.0)


class TestComputeAll:
    def test_compute_all_returns_all_indicators(self):
        prices = [100 + i * 0.3 for i in range(50)]
        result = compute_all(prices)
        assert len(result.ema_fast) == 50
        assert len(result.ema_slow) == 50
        assert len(result.rsi) == 50
        assert len(result.macd_line) == 50
        assert len(result.bb_upper) == 50
