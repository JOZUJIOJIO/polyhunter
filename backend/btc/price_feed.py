"""
BTC 实时价格 + 技术指标
"""

import statistics
from datetime import datetime, timezone

import httpx


class BTCPriceFeed:
    """获取 BTC 实时价格和历史 K 线数据"""

    async def get_current_price(self) -> float:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()["bitcoin"]["usd"]

    async def get_ohlcv_24h(self) -> list[dict]:
        """获取最近 24 小时的 1 小时 K 线（从 CoinGecko）"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "usd", "days": "1", "interval": "hourly"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

        prices = data.get("prices", [])
        return [{"timestamp": p[0], "price": p[1]} for p in prices]

    async def get_ohlcv_7d(self) -> list[dict]:
        """获取最近 7 天的 1 小时 K 线"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "usd", "days": "7", "interval": "hourly"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        prices = data.get("prices", [])
        return [{"timestamp": p[0], "price": p[1]} for p in prices]


def compute_indicators(prices: list[float]) -> dict:
    """计算技术指标"""
    if len(prices) < 14:
        return {}

    current = prices[-1]
    high_24h = max(prices[-24:]) if len(prices) >= 24 else max(prices)
    low_24h = min(prices[-24:]) if len(prices) >= 24 else min(prices)

    # SMA (Simple Moving Average)
    sma_7 = statistics.mean(prices[-7:])
    sma_24 = statistics.mean(prices[-24:]) if len(prices) >= 24 else statistics.mean(prices)

    # EMA 12 & 26
    ema_12 = _ema(prices, 12)
    ema_26 = _ema(prices, 26) if len(prices) >= 26 else ema_12

    # MACD
    macd = ema_12 - ema_26
    signal_line = _ema(prices[-9:], 9) - _ema(prices[-9:], 9) if len(prices) >= 9 else 0
    # Simplified: MACD histogram
    macd_histogram = macd

    # RSI (14 period)
    rsi = _rsi(prices, 14)

    # Bollinger Bands (20 period, 2 std)
    period = min(20, len(prices))
    bb_mean = statistics.mean(prices[-period:])
    bb_std = statistics.stdev(prices[-period:]) if period > 1 else 0
    bb_upper = bb_mean + 2 * bb_std
    bb_lower = bb_mean - 2 * bb_std

    # 波动率 (24h)
    returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
    volatility = statistics.stdev(returns[-24:]) * 100 if len(returns) >= 24 else 0

    # 趋势方向
    if len(prices) >= 24:
        trend_24h = (current - prices[-24]) / prices[-24] * 100
    else:
        trend_24h = 0

    return {
        "current_price": current,
        "high_24h": high_24h,
        "low_24h": low_24h,
        "sma_7h": round(sma_7, 2),
        "sma_24h": round(sma_24, 2),
        "ema_12": round(ema_12, 2),
        "ema_26": round(ema_26, 2),
        "macd": round(macd, 2),
        "rsi_14": round(rsi, 2),
        "bb_upper": round(bb_upper, 2),
        "bb_lower": round(bb_lower, 2),
        "bb_mean": round(bb_mean, 2),
        "volatility_24h": round(volatility, 4),
        "trend_24h_pct": round(trend_24h, 2),
        "above_sma_24": current > sma_24,
        "rsi_signal": "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性"),
        "macd_signal": "看涨" if macd > 0 else "看跌",
    }


def _ema(prices: list[float], period: int) -> float:
    if len(prices) < period:
        return statistics.mean(prices)
    multiplier = 2 / (period + 1)
    ema = statistics.mean(prices[:period])
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def _rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent = changes[-period:]
    gains = [c for c in recent if c > 0]
    losses = [-c for c in recent if c < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
