"""
蒙特卡洛价格路径模拟
基于几何布朗运动预测 BTC 在剩余时间内的价格分布
"""

import math
import random
from dataclasses import dataclass


@dataclass
class SimulationResult:
    prob_up: float          # 收盘 ≥ 开盘的概率
    prob_down: float        # 收盘 < 开盘的概率
    expected_close: float   # 预期收盘价
    confidence: int         # 置信度 0-100
    paths_up: int           # 上涨路径数
    paths_down: int         # 下跌路径数


def simulate_price_paths(
    current_price: float,
    open_price: float,
    volatility_per_second: float,
    seconds_remaining: int,
    n_simulations: int = 1000,
    drift: float | None = None,
) -> SimulationResult:
    """
    蒙特卡洛模拟 BTC 剩余时间内的价格路径

    Args:
        current_price: 当前 BTC 价格
        open_price: 5分钟窗口开盘价
        volatility_per_second: 每秒波动率 (从 compute_realtime_volatility 获取)
        seconds_remaining: 距离窗口结束的秒数
        n_simulations: 模拟路径数量
        drift: 漂移率 (None = 基于当前趋势自动计算)

    Returns:
        SimulationResult 含涨跌概率和预期收盘价
    """
    if seconds_remaining <= 0:
        # 已结束，直接判断
        is_up = current_price >= open_price
        return SimulationResult(
            prob_up=1.0 if is_up else 0.0,
            prob_down=0.0 if is_up else 1.0,
            expected_close=current_price,
            confidence=99,
            paths_up=n_simulations if is_up else 0,
            paths_down=0 if is_up else n_simulations,
        )

    # 自动计算漂移率：基于当前价相对开盘价的趋势
    if drift is None:
        elapsed_return = (current_price - open_price) / open_price
        # 趋势延续假设：当前方向有轻微惯性
        drift = elapsed_return * 0.1 / max(seconds_remaining, 1)

    dt = 1.0  # 每步 1 秒
    paths_up = 0
    closing_prices = []

    for _ in range(n_simulations):
        price = current_price
        for _ in range(seconds_remaining):
            # 几何布朗运动: dS/S = μdt + σdW
            random_shock = random.gauss(0, 1)
            price *= math.exp(
                (drift - 0.5 * volatility_per_second**2) * dt
                + volatility_per_second * math.sqrt(dt) * random_shock
            )

        closing_prices.append(price)
        if price >= open_price:
            paths_up += 1

    paths_down = n_simulations - paths_up
    prob_up = paths_up / n_simulations
    expected_close = sum(closing_prices) / len(closing_prices)

    # 置信度：概率越极端，越确定
    deviation = abs(prob_up - 0.5) * 2  # 0 到 1
    confidence = min(int(50 + deviation * 40), 90)

    return SimulationResult(
        prob_up=round(prob_up, 4),
        prob_down=round(1 - prob_up, 4),
        expected_close=round(expected_close, 2),
        confidence=confidence,
        paths_up=paths_up,
        paths_down=paths_down,
    )
