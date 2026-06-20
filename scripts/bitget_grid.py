#!/usr/bin/env python3
"""Bitget grid trading bot — places buy/sell orders at grid levels.

Usage:
    python -m scripts.bitget_grid --symbol BTCUSDT --lower 80000 --upper 90000 --grids 10 --size 10
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Settings
from backend.db.database import get_session_factory, init_db
from backend.db.models import BitgetTrade
from backend.exchanges.base import OrderRequest, OrderSide, OrderType
from backend.exchanges.bitget.adapter import BitgetAdapter
from backend.notify.telegram import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bitget_grid")


class GridTrader:
    def __init__(
        self,
        settings: Settings,
        symbol: str,
        lower: float,
        upper: float,
        grids: int,
        size_usd: float,
        dry_run: bool = False,
    ):
        self.settings = settings
        self.symbol = symbol
        self.lower = lower
        self.upper = upper
        self.grids = grids
        self.size_usd = size_usd
        self.dry_run = dry_run
        self.adapter = BitgetAdapter(settings)
        self.notifier = TelegramNotifier(settings)
        self._session_factory = get_session_factory(settings)
        self._grid_levels: list[float] = []
        self._active_orders: dict[float, str] = {}  # price -> order_id

    def _compute_grid(self) -> list[float]:
        step = (self.upper - self.lower) / self.grids
        levels = [self.lower + step * i for i in range(self.grids + 1)]
        return levels

    async def run(self):
        self._grid_levels = self._compute_grid()
        logger.info(
            f"Grid bot: {self.symbol} range=[${self.lower:,.0f}, ${self.upper:,.0f}] "
            f"grids={self.grids} size=${self.size_usd}"
        )
        logger.info(f"Grid levels: {['$' + f'{l:,.0f}' for l in self._grid_levels]}")

        if self.notifier.enabled:
            await self.notifier.send(
                f"\U0001f4ca <b>Grid Bot Started</b>\n"
                f"\U0001f4b1 Symbol: {self.symbol}\n"
                f"\U0001f4c9 Lower: ${self.lower:,.0f}\n"
                f"\U0001f4c8 Upper: ${self.upper:,.0f}\n"
                f"\U0001f522 Grids: {self.grids}\n"
                f"\U0001f4b0 Size per grid: ${self.size_usd}"
            )

        # Monitor loop
        try:
            while True:
                await self._check_and_place()
                await asyncio.sleep(30)  # Check every 30 seconds
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.adapter.close()
            await self.notifier.close()

    async def _check_and_place(self):
        try:
            ticker = await self.adapter.get_ticker(self.symbol)
            price = ticker.last_price
        except Exception as e:
            logger.error(f"Failed to get ticker: {e}")
            return

        # Find nearest grid level below current price → place BUY
        # Find nearest grid level above current price → place SELL
        for level in self._grid_levels:
            if level in self._active_orders:
                continue

            if level < price * 0.999:
                # Place BUY limit at this level
                await self._place_grid_order(level, "BUY")
            elif level > price * 1.001:
                # Place SELL limit at this level
                await self._place_grid_order(level, "SELL")

    async def _place_grid_order(self, grid_price: float, side: str):
        size = self.size_usd / grid_price
        if size <= 0:
            return

        logger.info(f"Grid {side} @ ${grid_price:,.2f} size={size:.6f}")

        if self.dry_run:
            self._active_orders[grid_price] = f"dry-{grid_price}"
            return

        try:
            order_req = OrderRequest(
                symbol=self.symbol,
                side=OrderSide(side),
                order_type=OrderType.LIMIT,
                size=size,
                price=grid_price,
            )
            result = await self.adapter.place_order(order_req)
            self._active_orders[grid_price] = result.order_id

            # Save trade
            session = self._session_factory()
            try:
                trade = BitgetTrade(
                    symbol=self.symbol,
                    side=side,
                    order_type="LIMIT",
                    price=grid_price,
                    size=size,
                    cost=self.size_usd,
                    status=result.status.value,
                    order_id=result.order_id,
                    strategy="GRID",
                )
                session.add(trade)
                session.commit()
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Grid order failed @ ${grid_price:,.2f}: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Bitget grid trader")
    parser.add_argument("--symbol", type=str, required=True)
    parser.add_argument("--lower", type=float, required=True, help="Lower price bound")
    parser.add_argument("--upper", type=float, required=True, help="Upper price bound")
    parser.add_argument("--grids", type=int, default=10, help="Number of grids")
    parser.add_argument("--size", type=float, default=10.0, help="USD per grid level")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    init_db(settings)

    trader = GridTrader(
        settings=settings,
        symbol=args.symbol,
        lower=args.lower,
        upper=args.upper,
        grids=args.grids,
        size_usd=args.size,
        dry_run=args.dry_run,
    )
    await trader.run()


if __name__ == "__main__":
    asyncio.run(main())
