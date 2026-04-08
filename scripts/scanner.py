"""
PolyHunter 自动扫描器
=====================
每隔固定时间自动执行：
1. 同步市场数据
2. 套利信号扫描
3. AI 预测信号扫描

用法：
  python scripts/scanner.py              # 默认每 60 分钟扫描一次
  python scripts/scanner.py --interval 30  # 每 30 分钟扫描一次
  python scripts/scanner.py --once         # 只扫描一次
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from backend.config import Settings
from backend.db.database import init_db, get_session_factory
from backend.db.models import Market, Signal, Trade
from backend.crawler.market_crawler import MarketCrawler
from backend.signals.arbitrage import ArbitrageDetector
from backend.signals.ai_predictor import AIPredictorDetector

AUTO_TRADE_CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auto_trade_config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scanner")


def run_scan(settings: Settings):
    Session = get_session_factory(settings)
    session = Session()
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")

    logger.info(f"{'='*50}")
    logger.info(f"开始扫描 ({now} UTC)")
    logger.info(f"{'='*50}")

    # 1. 同步市场
    logger.info("第 1 步：同步市场数据...")
    try:
        crawler = MarketCrawler(session=session)
        count = asyncio.run(crawler.sync_markets())
        total = session.query(Market).filter(Market.active == True).count()
        logger.info(f"  同步完成：{count} 个市场更新，共 {total} 个活跃市场")
    except Exception as e:
        logger.error(f"  市场同步失败: {e}")

    # 2. 套利扫描
    logger.info("第 2 步：套利信号扫描...")
    try:
        arb = ArbitrageDetector(session=session, settings=settings)
        arb_signals = arb.detect()
        if arb_signals:
            arb.save_signals(arb_signals)
            logger.info(f"  发现 {len(arb_signals)} 个套利信号！")
            for s in arb_signals:
                detail = json.loads(s.source_detail)
                logger.info(f"    市场 {s.market_id}: 边际 {s.edge_pct}%")
        else:
            logger.info("  无套利机会")
    except Exception as e:
        logger.error(f"  套利扫描失败: {e}")

    # 3. AI 预测扫描
    if settings.OPENROUTER_API_KEY:
        logger.info("第 3 步：AI 预测信号扫描...")
        try:
            ai = AIPredictorDetector(session=session, settings=settings)
            ai_signals = ai.detect()
            if ai_signals:
                ai.save_signals(ai_signals)
                logger.info(f"  发现 {len(ai_signals)} 个 AI 信号！")
                for s in ai_signals:
                    detail = json.loads(s.source_detail)
                    market = session.get(Market, s.market_id)
                    q = market.question[:50] if market else s.market_id
                    dir_cn = "被低估" if detail["direction"] == "UNDERPRICED" else "被高估"
                    logger.info(f"    {q}")
                    logger.info(f"      AI={detail['ai_probability']:.0%} 市场={detail['market_price']:.0%} {dir_cn} 边际{s.edge_pct}%")
            else:
                logger.info("  AI 未发现定价偏差")
        except Exception as e:
            logger.error(f"  AI 扫描失败: {e}")
    else:
        logger.info("第 3 步：跳过 AI 扫描（未配置 OPENROUTER_API_KEY）")

    # 4. 自动下单
    all_new_signals = session.query(Signal).filter(Signal.status == "NEW").all()
    auto_trade_config = _load_auto_trade_config()

    if auto_trade_config.get("enabled") and all_new_signals:
        logger.info("第 4 步：自动下单...")
        min_conf = auto_trade_config.get("min_confidence", 70)
        min_edge = auto_trade_config.get("min_edge_pct", 5.0)
        size_usd = auto_trade_config.get("size_usd", 5.0)

        qualified = [
            s for s in all_new_signals
            if s.confidence >= min_conf and s.edge_pct >= min_edge
        ]

        if qualified:
            logger.info(f"  {len(qualified)} 个信号满足自动下单条件 (置信度>={min_conf}, 边际>={min_edge}%)")
            for s in qualified:
                market = session.get(Market, s.market_id)
                if not market:
                    continue

                detail = json.loads(s.source_detail) if s.source_detail else {}
                direction = detail.get("direction", "UNDERPRICED")
                token_id = market.token_id_yes if direction == "UNDERPRICED" else market.token_id_no
                price = s.current_price
                size = round(size_usd / price, 2) if price > 0 else 0

                trade = Trade(
                    signal_id=s.id,
                    market_id=s.market_id,
                    token_id=token_id,
                    side="BUY",
                    price=price,
                    size=size,
                    cost=round(price * size, 4),
                    status="PENDING",
                )
                session.add(trade)
                s.status = "ACTED"
                q = market.question[:40] if market else s.market_id
                logger.info(f"    下单: {q} | BUY @ ${price:.2f} x {size} = ${price*size:.2f}")

            session.commit()
            logger.info(f"  已提交 {len(qualified)} 笔订单")
        else:
            logger.info(f"  {len(all_new_signals)} 个新信号均未达到自动下单条件")
    elif not auto_trade_config.get("enabled"):
        total_new = len(all_new_signals)
        if total_new > 0:
            logger.info(f"自动下单: 关闭 (有 {total_new} 个待处理信号，请在设置中开启)")

    logger.info("扫描完成")
    logger.info("")

    session.close()


def _load_auto_trade_config() -> dict:
    if os.path.exists(AUTO_TRADE_CONFIG):
        with open(AUTO_TRADE_CONFIG) as f:
            return json.load(f)
    return {"enabled": False, "min_confidence": 70, "min_edge_pct": 5.0, "size_usd": 5.0}


def main():
    parser = argparse.ArgumentParser(description="PolyHunter 自动扫描器")
    parser.add_argument("--interval", type=int, default=60, help="扫描间隔（分钟），默认 60")
    parser.add_argument("--once", action="store_true", help="只扫描一次")
    args = parser.parse_args()

    settings = Settings()
    init_db(settings)

    logger.info(f"PolyHunter 扫描器启动")
    logger.info(f"  扫描间隔: {'单次' if args.once else f'每 {args.interval} 分钟'}")
    logger.info(f"  AI 模型: {settings.AI_MODEL}")
    logger.info(f"  AI 每次最多分析: {settings.AI_MAX_MARKETS_PER_RUN} 个市场")
    logger.info(f"  信号阈值: 套利>{settings.RISK_MIN_EDGE_PCT}% AI>{settings.AI_EDGE_THRESHOLD_PCT}%")
    logger.info("")

    if args.once:
        run_scan(settings)
    else:
        while True:
            try:
                run_scan(settings)
            except Exception as e:
                logger.error(f"扫描异常: {e}")
            logger.info(f"下次扫描: {args.interval} 分钟后")
            time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
