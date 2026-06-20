#!/usr/bin/env python3
"""Standalone price monitor — watches prices and sends alerts.

Usage:
    python -m scripts.price_monitor [--symbols BTCUSDT,ETHUSDT] [--alert-pct 2.0]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Settings
from backend.exchanges.bitget.adapter import BitgetAdapter
from backend.monitor.price_monitor import PriceMonitor
from backend.notify.telegram import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("price_monitor")


async def main():
    parser = argparse.ArgumentParser(description="Price monitor")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols")
    parser.add_argument("--alert-pct", type=float, default=None, help="Alert threshold %")
    args = parser.parse_args()

    settings = Settings()

    if args.alert_pct is not None:
        settings.MONITOR_ALERT_CHANGE_PCT = args.alert_pct

    symbols = (args.symbols or settings.BITGET_SYMBOLS).split(",")
    symbols = [s.strip() for s in symbols if s.strip()]

    adapter = BitgetAdapter(settings)
    notifier = TelegramNotifier(settings)
    monitor = PriceMonitor(adapter, notifier, settings)

    logger.info(f"Starting price monitor: {symbols}")
    if notifier.enabled:
        await notifier.send(
            f"\U0001f4e1 <b>Price Monitor Started</b>\n"
            f"\U0001f4b1 Symbols: {', '.join(symbols)}\n"
            f"\U0001f514 Alert threshold: {settings.MONITOR_ALERT_CHANGE_PCT}%"
        )

    # Print prices periodically
    async def print_prices():
        while True:
            await asyncio.sleep(30)
            for sym in symbols:
                state = monitor.get_state(sym)
                if state and state.last_price > 0:
                    change = 0.0
                    if state.base_price > 0:
                        change = (state.last_price - state.base_price) / state.base_price * 100
                    logger.info(
                        f"{sym}: ${state.last_price:,.2f} "
                        f"(change: {change:+.2f}%, "
                        f"H: ${state.high_since_start:,.2f}, "
                        f"L: ${state.low_since_start:,.2f})"
                    )

    await monitor.start(symbols)

    try:
        await print_prices()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await monitor.stop()
        await adapter.close()
        await notifier.close()


if __name__ == "__main__":
    asyncio.run(main())
