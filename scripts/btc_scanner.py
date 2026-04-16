"""
PolyHunter BTC 日级预测扫描器
==============================
1. 获取 BTC 实时价格和技术指标
2. 扫描 Polymarket 上今天/明天到期的 BTC 价格市场
3. AI 分析每个关口能否突破
4. 生成信号并保存

用法:
  python scripts/btc_scanner.py              # 扫描一次
  python scripts/btc_scanner.py --loop 30    # 每30分钟扫描一次
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import httpx

from backend.config import Settings
from backend.db.database import init_db, get_session_factory
from backend.db.models import Market, Signal
from backend.btc.price_feed import BTCPriceFeed, compute_indicators
from backend.btc.predictor import BTCPredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("btc_scanner")


async def get_btc_daily_markets() -> list[dict]:
    """获取 Polymarket 上近几天到期的 BTC 价格市场"""
    async with httpx.AsyncClient() as client:
        events = []
        for offset in range(0, 500, 100):
            resp = await client.get(
                "https://gamma-api.polymarket.com/events",
                params={"active": "true", "closed": "false", "limit": 100, "offset": offset,
                        "order": "volume24hr", "ascending": "false"},
                timeout=30,
            )
            batch = resp.json()
            if not batch:
                break
            events.extend(batch)

    now = datetime.now(timezone.utc)
    markets = []

    for event in events:
        title = event.get("title", "").lower()
        if not any(kw in title for kw in ["bitcoin above", "price will bitcoin", "btc above"]):
            continue

        for m in event.get("markets", []):
            try:
                end_str = m.get("endDate", "")
                if not end_str:
                    continue
                end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

                # 要 30 天内到期的
                if end_date < now or end_date > now + timedelta(days=30):
                    continue

                prices = json.loads(m.get("outcomePrices", "[]"))
                clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                group = m.get("groupItemTitle", "")
                liq = float(m.get("liquidityClob", 0))

                # 提取价格关口
                nums = "".join(c for c in group.replace(",", "") if c.isdigit())
                threshold = int(nums) if nums else 0
                if threshold < 1000:
                    continue

                markets.append({
                    "event_title": event.get("title", ""),
                    "group": group,
                    "threshold": threshold,
                    "yes": float(prices[0]) if prices else 0,
                    "no": float(prices[1]) if len(prices) > 1 else 0,
                    "liquidity": liq,
                    "end_date": end_str[:10],
                    "market_id": m["id"],
                    "token_yes": clob_ids[0] if clob_ids else "",
                    "token_no": clob_ids[1] if len(clob_ids) > 1 else "",
                    "condition_id": m.get("conditionId", ""),
                })
            except Exception:
                continue

    markets.sort(key=lambda x: x["threshold"])
    return markets


def run_btc_scan(settings: Settings):
    logger.info("=" * 55)
    logger.info("BTC 日级预测扫描")
    logger.info("=" * 55)

    # 1. 获取 BTC 价格和指标
    logger.info("获取 BTC 价格和技术指标...")
    feed = BTCPriceFeed()

    try:
        price_data = asyncio.run(feed.get_ohlcv_7d())
        prices = [p["price"] for p in price_data]
        current_price = prices[-1]
        indicators = compute_indicators(prices)
    except Exception as e:
        logger.error(f"获取 BTC 数据失败: {e}")
        return

    logger.info(f"  BTC 当前价: ${current_price:,.0f}")
    logger.info(f"  RSI(14): {indicators.get('rsi_14', '?')} ({indicators.get('rsi_signal', '?')})")
    logger.info(f"  MACD: {indicators.get('macd', '?')} ({indicators.get('macd_signal', '?')})")
    logger.info(f"  24h 趋势: {indicators.get('trend_24h_pct', '?')}%")
    logger.info(f"  布林带: ${indicators.get('bb_lower', 0):,.0f} - ${indicators.get('bb_upper', 0):,.0f}")
    logger.info("")

    # 2. 获取 Polymarket BTC 市场
    logger.info("获取 Polymarket BTC 日级市场...")
    try:
        btc_markets = asyncio.run(get_btc_daily_markets())
    except Exception as e:
        logger.error(f"获取 Polymarket 市场失败: {e}")
        return

    if not btc_markets:
        logger.info("  未找到近 3 天内到期的 BTC 价格市场")
        return

    # 筛选有意义的关口（当前价 ±15% 范围内）
    interesting = []
    for m in btc_markets:
        diff_pct = abs(m["threshold"] - current_price) / current_price * 100
        if diff_pct < 15 and m["liquidity"] > 500:
            interesting.append(m)

    logger.info(f"  找到 {len(btc_markets)} 个 BTC 市场 (30天内到期)，{len(interesting)} 个在可交易范围内")
    logger.info("")

    if not interesting:
        logger.info("  当前价附近没有有流动性的关口")
        return

    # 3. AI 分析每个关口
    logger.info("AI 分析各关口...")
    predictor = BTCPredictor(settings=settings)
    init_db(settings)
    Session = get_session_factory(settings)
    session = Session()

    signals_found = 0

    for m in interesting:
        diff = m["threshold"] - current_price
        direction = "突破" if diff > 0 else "跌破"
        diff_pct = diff / current_price * 100

        logger.info(f"  分析: ${m['group']} ({direction}, 差{diff_pct:+.1f}%, 到期{m['end_date']})")

        result = predictor.predict(
            indicators=indicators,
            threshold=m["threshold"],
            direction=direction,
            market_yes=m["yes"],
            market_no=m["no"],
        )

        if not result:
            logger.warning(f"    AI 分析失败")
            continue

        ai_prob = result["probability"]
        market_price = m["yes"]
        edge = abs(ai_prob - market_price)
        edge_pct = edge * 100

        pred_cn = "能" if result["prediction"] == "YES" else "不能"
        logger.info(f"    AI 判断: {pred_cn}{direction} (概率{ai_prob:.0%}, 市场{market_price:.0%}, 边际{edge_pct:.1f}%)")
        logger.info(f"    理由: {result['reasoning']}")

        # 生成信号（边际 > 5%）
        if edge_pct >= settings.AI_EDGE_THRESHOLD_PCT:
            if ai_prob > market_price:
                action = f"买 YES (AI看涨到${m['threshold']:,})"
            else:
                action = f"买 NO (AI看跌不到${m['threshold']:,})"

            # 确保市场在数据库中
            existing = session.get(Market, m["market_id"])
            if not existing:
                db_market = Market(
                    id=m["market_id"],
                    condition_id=m.get("condition_id", ""),
                    token_id_yes=m["token_yes"],
                    token_id_no=m["token_no"],
                    question=f"Bitcoin above ${m['group']} on {m['end_date']}?",
                    category="crypto",
                    active=True,
                    last_price_yes=m["yes"],
                    last_price_no=m["no"],
                    liquidity=m["liquidity"],
                )
                session.add(db_market)
                session.commit()

            signal = Signal(
                market_id=m["market_id"],
                type="AI_PREDICTION",
                source_detail=json.dumps({
                    "ai_probability": ai_prob,
                    "market_price": market_price,
                    "edge_pct": round(edge_pct, 2),
                    "direction": "UNDERPRICED" if ai_prob > market_price else "OVERPRICED",
                    "confidence": result["confidence"],
                    "reasoning": result["reasoning"],
                    "btc_price": current_price,
                    "threshold": m["threshold"],
                    "action": action,
                    "indicators": {
                        "rsi": indicators.get("rsi_14"),
                        "macd_signal": indicators.get("macd_signal"),
                        "trend_24h": indicators.get("trend_24h_pct"),
                    },
                }),
                current_price=market_price,
                fair_value=round(ai_prob, 4),
                edge_pct=round(edge_pct, 2),
                confidence=result["confidence"],
                status="NEW",
            )
            session.add(signal)
            session.commit()
            signals_found += 1

            logger.info(f"    🔔 信号! {action} | 边际{edge_pct:.1f}% | 置信{result['confidence']}%")
        else:
            logger.info(f"    边际{edge_pct:.1f}% < 阈值{settings.AI_EDGE_THRESHOLD_PCT}%，不出信号")

        logger.info("")
        time.sleep(0.5)

    logger.info(f"扫描完成: 分析了 {len(interesting)} 个关口, 产生 {signals_found} 个信号")
    session.close()


def main():
    parser = argparse.ArgumentParser(description="PolyHunter BTC 日级预测")
    parser.add_argument("--loop", type=int, help="循环扫描间隔（分钟）")
    args = parser.parse_args()

    settings = Settings()

    if args.loop:
        logger.info(f"BTC 扫描器启动 (每 {args.loop} 分钟)")
        while True:
            try:
                run_btc_scan(settings)
            except Exception as e:
                logger.error(f"扫描异常: {e}")
            logger.info(f"下次扫描: {args.loop} 分钟后")
            time.sleep(args.loop * 60)
    else:
        run_btc_scan(settings)


if __name__ == "__main__":
    main()
