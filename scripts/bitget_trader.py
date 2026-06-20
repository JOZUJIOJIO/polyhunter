#!/usr/bin/env python3
"""Bitget auto-trader: monitors prices, detects signals, executes trades.

Features:
  - Real-time price monitoring via WebSocket
  - 4 strategies: EMA crossover, Bollinger Band, RSI, MACD
  - Automatic stop-loss (default 5%) and take-profit (default 10%)
  - Telegram notifications for all events
  - Circuit breaker on consecutive losses

Usage:
    python -m scripts.bitget_trader [--symbols BTCUSDT,ETHUSDT] [--dry-run]
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Settings
from backend.db.database import get_session_factory, init_db
from backend.db.models import BitgetTrade
from backend.exchanges.base import OrderRequest, OrderSide, OrderType
from backend.exchanges.bitget.adapter import BitgetAdapter
from backend.monitor.price_monitor import PriceMonitor
from backend.notify.telegram import TelegramNotifier
from backend.signals.bitget_strategies import BitgetStrategyEngine
from backend.trader.position_manager import PositionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bitget_trader")


class BitgetTrader:
    def __init__(self, settings: Settings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.adapter = BitgetAdapter(settings)
        self.notifier = TelegramNotifier(settings)
        self.monitor = PriceMonitor(self.adapter, self.notifier, settings)
        self.strategy_engine = BitgetStrategyEngine(settings)
        self.pos_manager = PositionManager(self.adapter, settings)
        self._session_factory = get_session_factory(settings)
        self._trade_count = 0
        self._circuit_tripped = False
        self._symbols: list[str] = []

    async def run(self, symbols: list[str]):
        self._symbols = symbols
        logger.info(f"Starting Bitget trader: symbols={symbols}, dry_run={self.dry_run}")
        logger.info(
            f"Risk: SL={self.settings.BITGET_STOP_LOSS_PCT}%, "
            f"TP={self.settings.BITGET_TAKE_PROFIT_PCT}%, "
            f"size=${self.settings.BITGET_DEFAULT_SIZE_USD}"
        )

        if self.notifier.enabled:
            await self.notifier.send(
                f"\U0001f680 <b>Bitget Trader Started</b>\n"
                f"\U0001f4b1 Symbols: {', '.join(symbols)}\n"
                f"\U0001f9ea Dry Run: {'Yes' if self.dry_run else 'No'}\n"
                f"\U0001f4ca Strategies: EMA, BB, RSI, MACD\n"
                f"\U0001f6d1 Stop-Loss: {self.settings.BITGET_STOP_LOSS_PCT}%\n"
                f"\U0001f4b0 Take-Profit: {self.settings.BITGET_TAKE_PROFIT_PCT}%\n"
                f"\U0001f4b5 Trade Size: ${self.settings.BITGET_DEFAULT_SIZE_USD}"
            )

        # Set leverage if futures
        if self.adapter.is_futures and self.settings.BITGET_LEVERAGE > 1:
            for sym in symbols:
                try:
                    await self.adapter.set_leverage(sym, self.settings.BITGET_LEVERAGE)
                except Exception as e:
                    logger.warning(f"Failed to set leverage for {sym}: {e}")

        # Start monitoring
        await self.monitor.start(symbols)

        # Register callbacks
        for sym in symbols:
            self.monitor.add_callback(sym, self._on_price)

        # Main loop: check SL/TP every second
        try:
            while True:
                await self._check_stop_loss_take_profit()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def _check_stop_loss_take_profit(self):
        """Check all open positions against SL/TP thresholds."""
        if self.pos_manager.open_count == 0:
            return

        # Gather current prices
        prices = {}
        for sym in self._symbols:
            state = self.monitor.get_state(sym)
            if state and state.last_price > 0:
                prices[sym] = state.last_price

        if not prices:
            return

        # Check positions
        if self.dry_run:
            # In dry-run, just log without executing
            for symbol, pos in self.pos_manager.positions.items():
                price = prices.get(symbol)
                if price is None:
                    continue
                pnl_pct = pos.pnl_pct(price)
                pnl_usd = pos.pnl_usd(price)

                if pnl_pct <= -self.settings.BITGET_STOP_LOSS_PCT:
                    logger.warning(
                        f"[DRY-RUN] STOP-LOSS would trigger: {symbol} "
                        f"PnL={pnl_pct:+.2f}% (${pnl_usd:+.2f})"
                    )
                    del self.pos_manager.positions[symbol]
                    await self._notify_close(pos, price, pnl_pct, pnl_usd, "STOP_LOSS")
                    return

                if pnl_pct >= self.settings.BITGET_TAKE_PROFIT_PCT:
                    logger.info(
                        f"[DRY-RUN] TAKE-PROFIT would trigger: {symbol} "
                        f"PnL={pnl_pct:+.2f}% (${pnl_usd:+.2f})"
                    )
                    del self.pos_manager.positions[symbol]
                    await self._notify_close(pos, price, pnl_pct, pnl_usd, "TAKE_PROFIT")
                    return
        else:
            closed = await self.pos_manager.check_positions(prices)
            for trade in closed:
                # Save to DB
                self._save_close_trade(trade)

                # Notify
                await self._notify_close_from_trade(trade)

    async def _on_price(self, symbol: str, price: float, timestamp: float):
        if self._circuit_tripped:
            return

        if not self.settings.BITGET_AUTO_TRADE_ENABLED and not self.dry_run:
            return

        # Don't open new position if we already have one for this symbol
        if self.pos_manager.has_position(symbol):
            return

        indicators = self.monitor.get_indicators(symbol)
        if indicators is None:
            return

        signals = self.strategy_engine.evaluate(symbol, price, indicators)

        for signal in signals:
            if signal.confidence < self.settings.BITGET_MIN_CONFIDENCE:
                continue
            if signal.edge_pct < self.settings.BITGET_MIN_EDGE_PCT:
                continue
            # Only take BUY signals in spot mode
            if not self.adapter.is_futures and signal.side != "BUY":
                continue

            logger.info(
                f"Signal: {signal.strategy.value} {signal.side} {symbol} "
                f"@ ${price:,.2f} conf={signal.confidence}% edge={signal.edge_pct:.2f}%"
            )

            if self.notifier.enabled:
                await self.notifier.notify_signal(
                    exchange="Bitget",
                    symbol=symbol,
                    signal_type=signal.strategy.value,
                    side=signal.side,
                    price=price,
                    edge_pct=signal.edge_pct,
                    confidence=signal.confidence,
                    reason=signal.reason,
                )

            if self.dry_run:
                # Simulate position tracking in dry-run
                size_usd = self.settings.BITGET_DEFAULT_SIZE_USD
                size = size_usd / price if price > 0 else 0
                self.pos_manager.open_position(
                    symbol=symbol,
                    side=signal.side,
                    entry_price=price,
                    size=size,
                    cost_usd=size_usd,
                    strategy=signal.strategy.value,
                )
                logger.info(
                    f"[DRY-RUN] Position opened: {signal.side} {size:.6f} {symbol} @ ${price:,.2f}"
                )
            else:
                await self._execute_trade(signal)
            break  # One trade per symbol per tick

    async def _execute_trade(self, signal):
        try:
            balance = await self.adapter.get_balance()
            usdt_balance = balance.get("USDT", 0)
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return

        margin_usd = min(self.settings.BITGET_DEFAULT_SIZE_USD, usdt_balance * 0.5)
        if margin_usd < 1:
            logger.debug(f"Insufficient balance for {signal.symbol}: ${usdt_balance:.2f}")
            return

        # Futures: buying power = margin × leverage
        leverage = self.settings.BITGET_LEVERAGE if self.adapter.is_futures else 1
        notional = margin_usd * leverage
        size = notional / signal.price if signal.price > 0 else 0
        size_usd = margin_usd

        if size <= 0:
            return

        # Pre-check: skip if notional can't meet minimum order for this symbol
        min_sizes = {"BTCUSDT": 0.001, "ETHUSDT": 0.01}
        min_size = min_sizes.get(signal.symbol, 0.01)
        if size < min_size and notional < min_size * signal.price:
            logger.debug(
                f"Skip {signal.symbol}: notional ${notional:.2f} < min order "
                f"{min_size} × ${signal.price:,.0f} = ${min_size * signal.price:,.0f}"
            )
            return

        logger.info(f"Order: margin=${margin_usd:.2f} × {leverage}x = ${notional:.2f} → {size:.6f} {signal.symbol}")

        try:
            order_req = OrderRequest(
                symbol=signal.symbol,
                side=OrderSide(signal.side),
                order_type=OrderType.MARKET,
                size=size,
            )
            result = await self.adapter.place_order(order_req)

            # Track position for SL/TP
            self.pos_manager.open_position(
                symbol=signal.symbol,
                side=signal.side,
                entry_price=result.price or signal.price,
                size=result.size,
                cost_usd=size_usd,
                order_id=result.order_id,
                strategy=signal.strategy.value,
            )

            # Save to DB
            session = self._session_factory()
            try:
                trade = BitgetTrade(
                    symbol=signal.symbol,
                    side=signal.side,
                    order_type="MARKET",
                    price=result.price or signal.price,
                    size=result.size,
                    cost=size_usd,
                    status=result.status.value,
                    order_id=result.order_id,
                    strategy=signal.strategy.value,
                )
                session.add(trade)
                session.commit()
            finally:
                session.close()

            self._trade_count += 1

            if self.notifier.enabled:
                await self.notifier.notify_order(
                    exchange="Bitget",
                    symbol=signal.symbol,
                    side=signal.side,
                    order_type="MARKET",
                    price=result.price or signal.price,
                    size=result.size,
                    order_id=result.order_id,
                    status=result.status.value,
                )

            logger.info(f"Trade executed: {result.order_id} {signal.side} {signal.symbol}")

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            if self.notifier.enabled:
                await self.notifier.notify_error("Bitget", str(e), f"Trade {signal.side} {signal.symbol}")

    def _save_close_trade(self, trade: dict):
        session = self._session_factory()
        try:
            record = BitgetTrade(
                symbol=trade["symbol"],
                side="SELL" if trade["side"] == "BUY" else "BUY",
                order_type="MARKET",
                price=trade["exit_price"],
                size=trade["size"],
                cost=trade["cost_usd"],
                status="FILLED",
                order_id=trade.get("order_id", ""),
                strategy=trade.get("reason", ""),
                pnl=trade["pnl_usd"],
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

    async def _notify_close(self, pos, price, pnl_pct, pnl_usd, reason):
        if self.notifier.enabled:
            await self.notifier.notify_position_closed(
                exchange="Bitget",
                symbol=pos.symbol,
                side=pos.side,
                entry_price=pos.entry_price,
                exit_price=price,
                size=pos.size,
                pnl=pnl_usd,
            )

    async def _notify_close_from_trade(self, trade: dict):
        if self.notifier.enabled:
            await self.notifier.notify_position_closed(
                exchange="Bitget",
                symbol=trade["symbol"],
                side=trade["side"],
                entry_price=trade["entry_price"],
                exit_price=trade["exit_price"],
                size=trade["size"],
                pnl=trade["pnl_usd"],
            )

    async def shutdown(self):
        logger.info("Shutting down Bitget trader...")

        # Log final position status
        if self.pos_manager.open_count > 0:
            prices = {}
            for sym in self._symbols:
                state = self.monitor.get_state(sym)
                if state:
                    prices[sym] = state.last_price
            logger.info(f"Open positions at shutdown:\n{self.pos_manager.status_summary(prices)}")

        await self.monitor.stop()
        await self.adapter.close()

        summary = (
            f"\U0001f6d1 <b>Bitget Trader Stopped</b>\n"
            f"\U0001f4ca Trades executed: {self._trade_count}\n"
            f"\U0001f4cb Positions still open: {self.pos_manager.open_count}\n"
            f"\U0001f4b0 Closed trades: {len(self.pos_manager.closed_trades)}"
        )
        if self.pos_manager.closed_trades:
            total_pnl = sum(t["pnl_usd"] for t in self.pos_manager.closed_trades)
            summary += f"\n\U0001f4b5 Total PnL: ${total_pnl:+,.2f}"

        logger.info(summary.replace("<b>", "").replace("</b>", ""))
        if self.notifier.enabled:
            await self.notifier.send(summary)
        await self.notifier.close()


async def main():
    parser = argparse.ArgumentParser(description="Bitget auto-trader")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no real trades)")
    args = parser.parse_args()

    settings = Settings()
    init_db(settings)

    symbols = (args.symbols or settings.BITGET_SYMBOLS).split(",")
    symbols = [s.strip() for s in symbols if s.strip()]

    trader = BitgetTrader(settings, dry_run=args.dry_run)
    await trader.run(symbols)


if __name__ == "__main__":
    asyncio.run(main())
