"""
Polymarket 5 分钟 BTC 市场发现
================================
正确方式：通过 Unix 时间戳直接计算市场 slug，然后查询 Gamma API 获取 token ID

市场 slug 格式: btc-updown-5m-{window_ts}
其中 window_ts = now - (now % 300)  （当前 5 分钟窗口的起始时间戳）

参考:
- https://github.com/Polymarket/py-clob-client/issues/244
- https://gist.github.com/Archetapp/7680adabc48f812a561ca79d73cbac69
"""

import json
import logging
import time as _time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
CLOB_BASE = "https://clob.polymarket.com"


def get_current_window_ts() -> int:
    """获取当前 5 分钟窗口的起始 Unix 时间戳"""
    now = int(_time.time())
    return now - (now % 300)


def get_next_window_ts() -> int:
    """获取下一个 5 分钟窗口的起始 Unix 时间戳"""
    return get_current_window_ts() + 300


def make_slug(window_ts: int, coin: str = "btc") -> str:
    """生成市场 slug"""
    return f"{coin}-updown-5m-{window_ts}"


def find_current_5m_market(proxy: str | None = None) -> dict | None:
    """
    查找当前活跃的 5 分钟 BTC 涨跌市场

    Returns:
        {
            "slug": str,
            "event_title": str,
            "market_id": str,
            "condition_id": str,
            "token_yes": str,       # UP token
            "token_no": str,        # DOWN token
            "yes_price": float,
            "no_price": float,
            "end_time": datetime,
            "seconds_left": int,
            "window_ts": int,
            "liquidity": float,
        }
        or None
    """
    window_ts = get_current_window_ts()
    slug = make_slug(window_ts)
    end_ts = window_ts + 300
    seconds_left = end_ts - int(_time.time())

    # 如果当前窗口快结束了（<10秒），查下一个
    if seconds_left < 10:
        window_ts = get_next_window_ts()
        slug = make_slug(window_ts)
        end_ts = window_ts + 300
        seconds_left = end_ts - int(_time.time())

    logger.debug(f"查找市场 slug: {slug} (剩余{seconds_left}s)")

    market_data = _fetch_market_by_slug(slug, proxy)
    if not market_data:
        # 尝试下一个窗口
        next_slug = make_slug(get_next_window_ts())
        market_data = _fetch_market_by_slug(next_slug, proxy)
        if market_data:
            slug = next_slug
            window_ts = get_next_window_ts()
            end_ts = window_ts + 300
            seconds_left = end_ts - int(_time.time())

    if not market_data:
        return None

    # 获取 CLOB 实时价格
    token_yes = market_data["token_yes"]
    token_no = market_data["token_no"]
    yes_price, no_price = _get_clob_prices(token_yes, token_no, proxy)

    return {
        "slug": slug,
        "event_title": market_data.get("question", f"BTC Up or Down 5M ({slug})"),
        "market_id": market_data["market_id"],
        "condition_id": market_data.get("condition_id", ""),
        "token_yes": token_yes,
        "token_no": token_no,
        "yes_price": yes_price,
        "no_price": no_price,
        "end_time": datetime.fromtimestamp(end_ts, tz=timezone.utc),
        "seconds_left": seconds_left,
        "window_ts": window_ts,
        "liquidity": market_data.get("liquidity", 0),
    }


def find_upcoming_5m_markets(count: int = 3, proxy: str | None = None) -> list[dict]:
    """查找接下来 N 个 5 分钟窗口的市场"""
    results = []
    base_ts = get_current_window_ts()

    for i in range(count):
        window_ts = base_ts + i * 300
        slug = make_slug(window_ts)
        market_data = _fetch_market_by_slug(slug, proxy)
        if market_data:
            end_ts = window_ts + 300
            seconds_left = end_ts - int(_time.time())
            results.append({
                "slug": slug,
                "window_ts": window_ts,
                "seconds_left": seconds_left,
                "market_id": market_data["market_id"],
                "token_yes": market_data["token_yes"],
                "token_no": market_data["token_no"],
            })

    return results


def _fetch_market_by_slug(slug: str, proxy: str | None = None) -> dict | None:
    """通过 slug 从 Gamma API 获取市场数据"""
    kwargs = {"timeout": 10}
    if proxy:
        kwargs["proxy"] = proxy

    try:
        with httpx.Client(**kwargs) as client:
            resp = client.get(GAMMA_MARKETS_URL, params={
                "slug": slug,
                "active": "true",
                "closed": "false",
            })
            resp.raise_for_status()
            markets = resp.json()

        if not markets or not isinstance(markets, list):
            return None

        m = markets[0]
        try:
            clob_ids = json.loads(m.get("clobTokenIds", "[]"))
        except (json.JSONDecodeError, TypeError):
            return None

        if len(clob_ids) < 2:
            return None

        return {
            "market_id": m.get("id", ""),
            "condition_id": m.get("conditionId", ""),
            "question": m.get("question", ""),
            "token_yes": clob_ids[0],   # 第一个 = UP/YES
            "token_no": clob_ids[1],    # 第二个 = DOWN/NO
            "liquidity": float(m.get("liquidityClob", 0)),
            "end_date": m.get("endDate", ""),
        }

    except Exception as e:
        logger.debug(f"获取市场 {slug} 失败: {e}")
        return None


def _get_clob_prices(token_yes: str, token_no: str, proxy: str | None = None) -> tuple[float, float]:
    """从 CLOB API 获取 YES/NO 实时价格"""
    kwargs = {"timeout": 5}
    if proxy:
        kwargs["proxy"] = proxy

    yes_price = 0.50
    no_price = 0.50

    try:
        with httpx.Client(**kwargs) as client:
            # YES 价格
            resp = client.get(f"{CLOB_BASE}/price", params={"token_id": token_yes, "side": "buy"})
            if resp.status_code == 200:
                yes_price = float(resp.json().get("price", 0.50))

            # NO 价格
            resp2 = client.get(f"{CLOB_BASE}/price", params={"token_id": token_no, "side": "buy"})
            if resp2.status_code == 200:
                no_price = float(resp2.json().get("price", 0.50))
    except Exception as e:
        logger.warning(f"获取 CLOB 价格失败: {e}")

    return yes_price, no_price
