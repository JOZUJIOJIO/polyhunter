"""蒙特卡洛模拟测试"""

from backend.btc.monte_carlo import simulate_price_paths, SimulationResult


class TestSimulatePricePaths:
    def test_returns_simulation_result(self):
        result = simulate_price_paths(
            current_price=80000,
            open_price=79500,
            volatility_per_second=0.00005,
            seconds_remaining=60,
            n_simulations=500,
        )
        assert isinstance(result, SimulationResult)
        assert 0 <= result.prob_up <= 1
        assert 0 <= result.prob_down <= 1
        assert abs(result.prob_up + result.prob_down - 1.0) < 0.001
        assert result.paths_up + result.paths_down == 500

    def test_zero_seconds_remaining_up(self):
        """已结束且价格高于开盘 → 100% 涨"""
        result = simulate_price_paths(
            current_price=80000,
            open_price=79000,
            volatility_per_second=0.0001,
            seconds_remaining=0,
        )
        assert result.prob_up == 1.0
        assert result.prob_down == 0.0
        assert result.confidence == 99

    def test_zero_seconds_remaining_down(self):
        """已结束且价格低于开盘 → 100% 跌"""
        result = simulate_price_paths(
            current_price=78000,
            open_price=79000,
            volatility_per_second=0.0001,
            seconds_remaining=0,
        )
        assert result.prob_up == 0.0
        assert result.prob_down == 1.0

    def test_strong_uptrend_bias(self):
        """价格大幅高于开盘时，涨的概率应偏高"""
        result = simulate_price_paths(
            current_price=81000,
            open_price=79000,
            volatility_per_second=0.00003,
            seconds_remaining=30,
            n_simulations=2000,
        )
        assert result.prob_up > 0.6

    def test_strong_downtrend_bias(self):
        """价格大幅低于开盘时，跌的概率应偏高"""
        result = simulate_price_paths(
            current_price=77000,
            open_price=79000,
            volatility_per_second=0.00003,
            seconds_remaining=30,
            n_simulations=2000,
        )
        assert result.prob_down > 0.6

    def test_confidence_range(self):
        result = simulate_price_paths(
            current_price=80000,
            open_price=80000,
            volatility_per_second=0.0001,
            seconds_remaining=120,
            n_simulations=1000,
        )
        assert 50 <= result.confidence <= 90

    def test_expected_close_reasonable(self):
        """预期收盘价应在合理范围内"""
        result = simulate_price_paths(
            current_price=80000,
            open_price=79500,
            volatility_per_second=0.00005,
            seconds_remaining=60,
            n_simulations=1000,
        )
        # 60 秒内不应偏离太远
        assert 79000 < result.expected_close < 81000

    def test_custom_drift(self):
        """自定义漂移率"""
        result = simulate_price_paths(
            current_price=80000,
            open_price=80000,
            volatility_per_second=0.00001,
            seconds_remaining=60,
            n_simulations=1000,
            drift=0.001,  # 强正漂移
        )
        assert result.prob_up > 0.5
