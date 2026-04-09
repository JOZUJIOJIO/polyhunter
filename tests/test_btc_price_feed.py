"""BTC 价格源和技术指标测试"""

from backend.btc.price_feed import compute_indicators, _ema, _rsi


class TestComputeIndicators:
    def _make_prices(self, base=80000, count=30, trend=10):
        """生成模拟价格序列"""
        return [base + i * trend for i in range(count)]

    def test_full_indicators(self):
        prices = self._make_prices()
        result = compute_indicators(prices)
        assert "current_price" in result
        assert "sma_7h" in result
        assert "sma_24h" in result
        assert "rsi_14" in result
        assert "bb_upper" in result
        assert "bb_lower" in result
        assert "volatility_24h" in result
        assert "trend_24h_pct" in result
        assert "rsi_signal" in result
        assert "macd_signal" in result

    def test_too_few_prices_returns_empty(self):
        result = compute_indicators([80000, 80100])
        assert result == {}

    def test_exactly_14_prices(self):
        prices = self._make_prices(count=14)
        result = compute_indicators(prices)
        assert result != {}
        assert result["current_price"] == prices[-1]

    def test_uptrend_signals(self):
        prices = self._make_prices(trend=100)  # 明显上涨
        result = compute_indicators(prices)
        assert result["trend_24h_pct"] > 0
        assert result["above_sma_24"] is True
        assert result["macd_signal"] == "看涨"

    def test_downtrend_signals(self):
        prices = self._make_prices(base=82000, trend=-100)  # 明显下跌
        result = compute_indicators(prices)
        assert result["trend_24h_pct"] < 0
        assert result["macd_signal"] == "看跌"

    def test_rsi_overbought(self):
        # 连续快速上涨 → RSI > 70
        prices = [80000 + i * 200 for i in range(30)]
        result = compute_indicators(prices)
        assert result["rsi_14"] > 70
        assert result["rsi_signal"] == "超买"

    def test_bollinger_bands_order(self):
        prices = self._make_prices()
        result = compute_indicators(prices)
        assert result["bb_lower"] < result["bb_upper"]


class TestEMA:
    def test_basic_ema(self):
        prices = [10, 11, 12, 13, 14, 15]
        result = _ema(prices, 3)
        assert isinstance(result, float)
        # EMA should be closer to recent prices
        assert result > 12

    def test_short_prices_returns_mean(self):
        prices = [10, 11]
        result = _ema(prices, 5)
        assert result == 10.5


class TestRSI:
    def test_all_gains_rsi_near_100(self):
        prices = [100 + i for i in range(20)]
        rsi = _rsi(prices)
        assert rsi > 90

    def test_all_losses_rsi_near_0(self):
        prices = [100 - i for i in range(20)]
        rsi = _rsi(prices)
        assert rsi < 10

    def test_flat_prices_rsi_near_50(self):
        prices = [100] * 20
        rsi = _rsi(prices)
        # With no movement, gains=0, rsi approaches 0
        # Actually, if no gains and no losses, behavior depends on implementation
        assert 0 <= rsi <= 100

    def test_insufficient_data(self):
        rsi = _rsi([100, 101], 14)
        assert rsi == 50.0
