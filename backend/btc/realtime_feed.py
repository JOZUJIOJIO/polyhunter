"""
Binance 实时 BTC 价格获取
使用 REST API 轮询（简单可靠，延迟 <1s）
"""

import statistics

import httpx

BINANCE_BASE = "https://api.binance.com"
BACKUP_BASE = "https://api4.binance.com"
# 国内可用备用源
CN_BINANCE = "https://data-api.binance.vision"


def get_btc_price(proxy: str | None = None) -> float:
    """获取 BTC/USDT 最新价格"""
    sources = [CN_BINANCE, BINANCE_BASE, BACKUP_BASE]
    for base in sources:
        try:
            kwargs = {"timeout": 5}
            if proxy:
                kwargs["proxy"] = proxy
            with httpx.Client(**kwargs) as client:
                resp = client.get(f"{base}/api/v3/ticker/price", params={"symbol": "BTCUSDT"})
                resp.raise_for_status()
                return float(resp.json()["price"])
        except Exception:
            continue
    # Fallback to CoinGecko
    kwargs2 = {"timeout": 10}
    if proxy:
        kwargs2["proxy"] = proxy
    with httpx.Client(**kwargs2) as client:
        resp = client.get("https://api.coingecko.com/api/v3/simple/price",
                          params={"ids": "bitcoin", "vs_currencies": "usd"})
        return resp.json()["bitcoin"]["usd"]


def get_btc_klines_1m(limit: int = 10, proxy: str | None = None) -> list[dict]:
    """获取最近 N 根 1 分钟 K 线"""
    sources = [CN_BINANCE, BINANCE_BASE, BACKUP_BASE]
    for base in sources:
        try:
            kwargs = {"timeout": 10}
            if proxy:
                kwargs["proxy"] = proxy
            with httpx.Client(**kwargs) as client:
                resp = client.get(
                    f"{base}/api/v3/klines",
                    params={"symbol": "BTCUSDT", "interval": "1m", "limit": limit},
                )
                resp.raise_for_status()
                data = resp.json()
                break
        except Exception:
            continue
    else:
        raise RuntimeError("All Binance endpoints failed")

    return [
        {
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in data
    ]


def compute_realtime_volatility(klines: list[dict]) -> float:
    """从 1 分钟 K 线计算实时波动率（每秒标准差）"""
    if len(klines) < 2:
        return 0.0001  # 默认极小波动率

    closes = [k["close"] for k in klines]
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]

    if not returns:
        return 0.0001

    # 1 分钟收益率标准差 → 转换为每秒波动率
    vol_1m = statistics.stdev(returns) if len(returns) > 1 else abs(returns[0])
    vol_per_second = vol_1m / (60 ** 0.5)

    return max(vol_per_second, 0.00001)
