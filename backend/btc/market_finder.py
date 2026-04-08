"""
Polymarket 5 分钟 BTC 市场发现
自动查找当前活跃的 "Bitcoin Up or Down" 5 分钟市场
"""

import json
import logging
from datetime import datetime, timezone, timedelta

import httpx

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"


def find_current_5m_market(proxy: str | None = None) -> dict | None:
    """
    查找当前活跃的 5 分钟 BTC 涨跌市场

    Returns:
        {
            "event_title": str,
            "market_id": str,
            "token_yes": str,     # YES (涨) token ID
            "token_no": str,      # NO (跌) token ID
            "yes_price": float,   # YES 当前价格 (市场赔率)
            "no_price": float,    # NO 当前价格
            "end_time": datetime, # 到期时间
            "seconds_left": int,  # 剩余秒数
            "liquidity": float,
        }
        or None if no market found
    """
    kwargs = {"timeout": 15}
    if proxy:
        kwargs["proxy"] = proxy

    try:
        with httpx.Client(**kwargs) as client:
            # 搜索多页找 5M 市场
            for offset in range(0, 500, 100):
                resp = client.get(
                    f"{GAMMA_BASE}/events",
                    params={
                        "active": "true",
                        "closed": "false",
                        "limit": 100,
                        "offset": offset,
                        "order": "volume24hr",
                        "ascending": "false",
                    },
                )
                resp.raise_for_status()
                events = resp.json()
                if not events:
                    break

                for event in events:
                    title = event.get("title", "")
                    # 匹配 5 分钟 BTC 涨跌市场
                    title_lower = title.lower()
                    if "bitcoin" not in title_lower:
                        continue
                    if "up or down" not in title_lower and "5m" not in title_lower:
                        continue

                    result = _parse_5m_event(event)
                    if result:
                        return result
    except Exception as e:
        logger.error(f"查找 5M 市场失败: {e}")

    return None


def find_upcoming_5m_markets(proxy: str | None = None) -> list[dict]:
    """查找所有即将到来的 5 分钟 BTC 市场（未来 15 分钟内到期的）"""
    kwargs = {"timeout": 15}
    if proxy:
        kwargs["proxy"] = proxy

    results = []
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=15)

    try:
        with httpx.Client(**kwargs) as client:
            for offset in range(0, 500, 100):
                resp = client.get(
                    f"{GAMMA_BASE}/events",
                    params={
                        "active": "true",
                        "closed": "false",
                        "limit": 100,
                        "offset": offset,
                        "order": "volume24hr",
                        "ascending": "false",
                    },
                )
                resp.raise_for_status()
                events = resp.json()
                if not events:
                    break

                for event in events:
                    title = event.get("title", "").lower()
                    if "bitcoin" not in title:
                        continue
                    if "up or down" not in title and "5m" not in title:
                        continue

                    parsed = _parse_5m_event(event, max_seconds=900)
                    if parsed:
                        results.append(parsed)

    except Exception as e:
        logger.error(f"查找 5M 市场失败: {e}")

    results.sort(key=lambda x: x["end_time"])
    return results


def _parse_5m_event(event: dict, max_seconds: int = 600) -> dict | None:
    """解析 5 分钟事件，返回市场数据或 None"""
    now = datetime.now(timezone.utc)
    title = event.get("title", "")

    for m in event.get("markets", []):
        end_str = m.get("endDate", "")
        if not end_str:
            continue

        try:
            end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        seconds_left = int((end_time - now).total_seconds())

        # 只要还没结束且在 max_seconds 秒内到期的
        if seconds_left <= 0 or seconds_left > max_seconds:
            continue

        try:
            prices = json.loads(m.get("outcomePrices", "[]"))
            clob_ids = json.loads(m.get("clobTokenIds", "[]"))
        except (json.JSONDecodeError, TypeError):
            continue

        if len(prices) < 2 or len(clob_ids) < 2:
            continue

        liq = float(m.get("liquidityClob", 0))

        return {
            "event_title": title,
            "market_id": m["id"],
            "token_yes": clob_ids[0],
            "token_no": clob_ids[1],
            "yes_price": float(prices[0]),
            "no_price": float(prices[1]),
            "end_time": end_time,
            "seconds_left": seconds_left,
            "liquidity": liq,
            "condition_id": m.get("conditionId", ""),
        }

    return None
