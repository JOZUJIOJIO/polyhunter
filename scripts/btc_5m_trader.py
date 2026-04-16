"""
PolyHunter BTC 5分钟自动交易器
================================
每 5 分钟一局，在最后 60 秒用蒙特卡洛模拟判断涨跌概率，
与 Polymarket 赔率对比，有边际就自动下注。

用法:
  python scripts/btc_5m_trader.py              # 实盘交易
  python scripts/btc_5m_trader.py --dry-run    # 模拟运行（不下单）
"""

import argparse
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
from backend.db.models import Market, Signal, Trade, Position
from backend.btc.realtime_feed import get_btc_price, get_btc_klines_1m, compute_realtime_volatility
from backend.btc.monte_carlo import simulate_price_paths
from backend.btc.market_finder import find_current_5m_market
from backend.trader.executor import OrderExecutor
from backend.trader.risk_manager import RiskManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("btc_5m")

# 统计
stats = {"rounds": 0, "trades": 0, "skipped": 0, "wins": 0, "losses": 0, "pnl": 0.0}

# 全局 DB（启动时初始化一次）
_session = None


def _get_session(settings: Settings):
    global _session
    if _session is None:
        init_db(settings)
        Session = get_session_factory(settings)
        _session = Session()
    return _session


def _get_wallet_balance(settings: Settings, proxy: str | None = None) -> float:
    """从链上查询 USDC 余额"""
    import httpx
    wallet = settings.POLYMARKET_FUNDER
    if not wallet:
        return 50.0  # fallback
    RPC = "https://1rpc.io/matic"
    USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
    USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    try:
        cd = "0x70a08231" + wallet[2:].lower().zfill(64)
        kwargs = {"timeout": 10, "verify": False}
        r1 = httpx.post(RPC, json={"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": USDC_NATIVE, "data": cd}, "latest"], "id": 1}, **kwargs)
        r2 = httpx.post(RPC, json={"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": USDC_E, "data": cd}, "latest"], "id": 2}, **kwargs)
        def safe_int(h):
            if not h or h == "0x": return 0
            return int(h, 16)
        usdc_n = safe_int(r1.json().get("result", "0x0")) / 1e6
        usdc_e = safe_int(r2.json().get("result", "0x0")) / 1e6
        total = usdc_n + usdc_e
        return total if total > 0 else 50.0
    except Exception:
        return 50.0


def run_one_round(settings: Settings, dry_run: bool = False):
    """执行一轮 5 分钟交易"""
    stats["rounds"] += 1
    proxy = settings.PROXY_URL if settings.PROXY_URL else None

    logger.info("=" * 55)
    logger.info(f"第 {stats['rounds']} 轮 | {datetime.now().strftime('%H:%M:%S')}")
    logger.info("=" * 55)

    # 1. 查找当前 5 分钟市场
    logger.info("查找 5 分钟 BTC 市场...")
    market = find_current_5m_market(proxy=proxy)

    if not market:
        logger.info("  未找到活跃的 5 分钟市场，等待下一轮")
        stats["skipped"] += 1
        return

    seconds_left = market["seconds_left"]
    logger.info(f"  找到: {market['event_title']}")
    logger.info(f"  YES(涨)=${market['yes_price']:.2f} NO(跌)=${market['no_price']:.2f}")
    logger.info(f"  到期: {market['end_time'].strftime('%H:%M:%S')} (剩余 {seconds_left}s)")
    logger.info(f"  流动性: ${market['liquidity']:,.0f}")

    # 2. 如果剩余时间太多，等到最后 N 秒再决策
    entry_before = settings.BTC_5M_ENTRY_SECONDS_BEFORE_END
    if seconds_left > entry_before + 10:
        wait = seconds_left - entry_before
        logger.info(f"  等待 {wait}s 到决策窗口...")
        time.sleep(wait)

    # 3. 获取实时 BTC 价格
    logger.info("获取实时 BTC 价格...")
    try:
        current_price = get_btc_price(proxy=proxy)
        klines = get_btc_klines_1m(limit=10, proxy=proxy)
        volatility = compute_realtime_volatility(klines)
    except Exception as e:
        logger.error(f"  获取价格失败: {e}")
        stats["skipped"] += 1
        return

    # 开盘价：用最早的 K 线推算（5分钟前）
    if len(klines) >= 5:
        open_price = klines[-5]["open"]
    else:
        open_price = klines[0]["open"]

    price_change = current_price - open_price
    price_change_pct = price_change / open_price * 100

    logger.info(f"  当前价: ${current_price:,.2f}")
    logger.info(f"  开盘价: ${open_price:,.2f}")
    logger.info(f"  变化: {price_change_pct:+.3f}%")
    logger.info(f"  波动率: {volatility:.6f}/s")

    # 4. 蒙特卡洛模拟
    # 重新计算剩余秒数
    now = datetime.now(timezone.utc)
    seconds_remaining = max(int((market["end_time"] - now).total_seconds()), 1)

    logger.info(f"蒙特卡洛模拟 (剩余{seconds_remaining}s, {settings.BTC_5M_SIMULATIONS}次)...")
    sim = simulate_price_paths(
        current_price=current_price,
        open_price=open_price,
        volatility_per_second=volatility,
        seconds_remaining=seconds_remaining,
        n_simulations=settings.BTC_5M_SIMULATIONS,
    )

    logger.info(f"  模拟结果: 涨{sim.prob_up:.1%} 跌{sim.prob_down:.1%}")
    logger.info(f"  预期收盘: ${sim.expected_close:,.2f}")
    logger.info(f"  置信度: {sim.confidence}%")

    # 5. 与市场赔率对比（扣除手续费）
    market_yes = market["yes_price"]  # 市场认为涨的概率
    market_no = market["no_price"]    # 市场认为跌的概率
    fee_pct = settings.POLYMARKET_FEE_PCT  # 默认 2%

    # 计算边际（扣除手续费后的净边际）
    edge_yes = sim.prob_up - market_yes - fee_pct / 100  # 正 = YES 被低估
    edge_no = sim.prob_down - market_no - fee_pct / 100  # 正 = NO 被低估
    best_edge = max(edge_yes, edge_no)
    best_side = "YES" if edge_yes >= edge_no else "NO"
    best_edge_pct = best_edge * 100

    logger.info(f"  市场赔率: YES={market_yes:.2f} NO={market_no:.2f}")
    logger.info(f"  AI 概率:  YES={sim.prob_up:.2f} NO={sim.prob_down:.2f}")
    logger.info(f"  最佳边际: {best_side} {best_edge_pct:+.1f}%")

    # 6. 决策
    min_edge = settings.BTC_5M_MIN_EDGE_PCT
    if best_edge_pct < min_edge:
        logger.info(f"  ❌ 边际 {best_edge_pct:.1f}% < 阈值 {min_edge}%，跳过")
        stats["skipped"] += 1
        return

    # 下注!
    bet_size = settings.BTC_5M_BET_SIZE_USD
    token_id = market["token_yes"] if best_side == "YES" else market["token_no"]
    buy_price = market_yes if best_side == "YES" else market_no
    shares = round(bet_size / buy_price, 2) if buy_price > 0 else 0

    direction_cn = "涨" if best_side == "YES" else "跌"
    logger.info(f"  ✅ 下注! 买 {best_side}({direction_cn}) ${bet_size} @ ${buy_price:.2f} ({shares}份)")

    if dry_run:
        logger.info(f"  [DRY RUN] 模拟下单，不实际执行")
        stats["trades"] += 1
        return

    # 7. 执行下单
    try:
        session = _get_session(settings)

        # 确保市场在 DB 中
        if not session.get(Market, market["market_id"]):
            db_market = Market(
                id=market["market_id"],
                condition_id=market.get("condition_id", ""),
                token_id_yes=market["token_yes"],
                token_id_no=market["token_no"],
                question=market["event_title"],
                category="crypto",
                active=True,
                last_price_yes=market_yes,
                last_price_no=market_no,
                liquidity=market["liquidity"],
            )
            session.add(db_market)
            session.commit()

        # 创建信号
        signal = Signal(
            market_id=market["market_id"],
            type="AI_PREDICTION",
            source_detail=json.dumps({
                "strategy": "btc_5m_monte_carlo",
                "btc_price": current_price,
                "open_price": open_price,
                "prob_up": sim.prob_up,
                "prob_down": sim.prob_down,
                "market_yes": market_yes,
                "market_no": market_no,
                "best_side": best_side,
                "edge_pct": round(best_edge_pct, 2),
                "volatility": volatility,
                "seconds_remaining": seconds_remaining,
                "simulations": settings.BTC_5M_SIMULATIONS,
                "fee_deducted_pct": fee_pct,
            }),
            current_price=buy_price,
            fair_value=sim.prob_up if best_side == "YES" else sim.prob_down,
            edge_pct=round(best_edge_pct, 2),
            confidence=sim.confidence,
            status="NEW",
        )
        session.add(signal)
        session.commit()

        # 查询真实余额
        wallet_balance = _get_wallet_balance(settings, proxy)
        logger.info(f"  钱包余额: ${wallet_balance:.2f}")

        # 5M 市场跳过到期缓冲检查（因为 5M 市场本身就在 5 分钟内到期）
        saved_expiry = settings.RISK_EXPIRY_BUFFER_HOURS
        settings.RISK_EXPIRY_BUFFER_HOURS = 0

        rm = RiskManager(session=session, settings=settings, total_balance=wallet_balance)
        executor = OrderExecutor(session=session, risk_manager=rm, settings=settings)
        trade = executor.execute(
            signal_id=signal.id,
            market_id=market["market_id"],
            token_id=token_id,
            side="BUY",
            price=buy_price,
            size=shares,
        )

        # 恢复到期缓冲
        settings.RISK_EXPIRY_BUFFER_HOURS = saved_expiry

        if trade and trade.status == "FILLED":
            logger.info(f"  订单成交! order_id={trade.order_id}")
            stats["trades"] += 1

            # 创建 Position 记录
            pos = Position(
                market_id=market["market_id"],
                token_id=token_id,
                side=best_side,
                avg_entry_price=buy_price,
                size=shares,
                current_price=buy_price,
                unrealized_pnl=0.0,
            )
            session.add(pos)
            session.commit()
        elif trade and trade.status == "CANCELLED":
            logger.info(f"  订单失败（可能被地区限制）")
        else:
            logger.info(f"  订单被风控拒绝")

    except Exception as e:
        logger.error(f"  下单异常: {e}")


def main():
    parser = argparse.ArgumentParser(description="BTC 5分钟自动交易器")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际下单")
    args = parser.parse_args()

    settings = Settings()

    logger.info("=" * 55)
    logger.info("  PolyHunter BTC 5分钟自动交易器")
    logger.info("=" * 55)
    logger.info(f"  模式: {'模拟' if args.dry_run else '实盘'}")
    logger.info(f"  单笔金额: ${settings.BTC_5M_BET_SIZE_USD}")
    logger.info(f"  最小边际: {settings.BTC_5M_MIN_EDGE_PCT}%")
    logger.info(f"  入场时机: 结束前 {settings.BTC_5M_ENTRY_SECONDS_BEFORE_END}s")
    logger.info(f"  模拟次数: {settings.BTC_5M_SIMULATIONS}")
    logger.info(f"  代理: {settings.PROXY_URL}")
    logger.info("")

    round_count = 0
    while True:
        try:
            run_one_round(settings, dry_run=args.dry_run)
        except Exception as e:
            logger.error(f"本轮异常: {e}")

        round_count += 1

        # 打印统计
        logger.info(f"  📊 累计: {stats['rounds']}轮 {stats['trades']}交易 {stats['skipped']}跳过")
        logger.info("")

        # 等到下一个 5 分钟窗口
        now = datetime.now(timezone.utc)
        # 对齐到下一个 5 分钟边界
        seconds_in_current = (now.minute % 5) * 60 + now.second
        wait = 300 - seconds_in_current + 10  # 多等 10 秒让新市场出现
        if wait > 300:
            wait -= 300

        logger.info(f"等待 {wait}s 到下一个 5 分钟窗口...")
        time.sleep(wait)


if __name__ == "__main__":
    main()
