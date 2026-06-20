"""Position manager with stop-loss and take-profit monitoring.

Tracks open Bitget positions and automatically closes them
when SL/TP thresholds are breached.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.config import Settings
from backend.exchanges.base import ExchangeAdapter, OrderRequest, OrderSide, OrderType

logger = logging.getLogger(__name__)


@dataclass
class TrackedPosition:
    symbol: str
    side: str           # "BUY" (long)
    entry_price: float
    size: float          # in base currency (e.g. BTC amount)
    cost_usd: float
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    order_id: str = ""
    strategy: str = ""

    def pnl_pct(self, current_price: float) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.side == "BUY":
            return (current_price - self.entry_price) / self.entry_price * 100
        else:  # SELL / short
            return (self.entry_price - current_price) / self.entry_price * 100

    def pnl_usd(self, current_price: float) -> float:
        if self.side == "BUY":
            return (current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - current_price) * self.size


class PositionManager:
    """Monitors open positions and enforces stop-loss / take-profit rules."""

    def __init__(self, exchange: ExchangeAdapter, settings: Settings | None = None):
        self.exchange = exchange
        self.settings = settings or Settings()
        self.positions: dict[str, TrackedPosition] = {}  # symbol -> position
        self.stop_loss_pct = self.settings.BITGET_STOP_LOSS_PCT
        self.take_profit_pct = self.settings.BITGET_TAKE_PROFIT_PCT
        self._closed_trades: list[dict] = []

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        cost_usd: float,
        order_id: str = "",
        strategy: str = "",
    ) -> TrackedPosition:
        pos = TrackedPosition(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            cost_usd=cost_usd,
            order_id=order_id,
            strategy=strategy,
        )
        self.positions[symbol] = pos
        logger.info(
            f"Position opened: {side} {size:.6f} {symbol} @ ${entry_price:,.2f} "
            f"(cost=${cost_usd:.2f}, SL={self.stop_loss_pct}%, TP={self.take_profit_pct}%)"
        )
        return pos

    async def check_positions(self, prices: dict[str, float]) -> list[dict]:
        """Check all positions against current prices. Returns list of closed trades."""
        closed = []
        for symbol, pos in list(self.positions.items()):
            price = prices.get(symbol)
            if price is None:
                continue

            pnl_pct = pos.pnl_pct(price)
            pnl_usd = pos.pnl_usd(price)

            # Stop-loss: close if loss exceeds threshold
            if pnl_pct <= -self.stop_loss_pct:
                logger.warning(
                    f"STOP-LOSS triggered: {symbol} pnl={pnl_pct:+.2f}% (${pnl_usd:+.2f}) "
                    f"entry=${pos.entry_price:,.2f} → current=${price:,.2f}"
                )
                result = await self._close_position(pos, price, "STOP_LOSS")
                if result:
                    closed.append(result)

            # Take-profit: close if profit exceeds threshold
            elif pnl_pct >= self.take_profit_pct:
                logger.info(
                    f"TAKE-PROFIT triggered: {symbol} pnl={pnl_pct:+.2f}% (${pnl_usd:+.2f}) "
                    f"entry=${pos.entry_price:,.2f} → current=${price:,.2f}"
                )
                result = await self._close_position(pos, price, "TAKE_PROFIT")
                if result:
                    closed.append(result)

        return closed

    async def _close_position(self, pos: TrackedPosition, current_price: float, reason: str) -> dict | None:
        """Close a position by placing a counter-order."""
        close_side = OrderSide.SELL if pos.side == "BUY" else OrderSide.BUY

        try:
            order = OrderRequest(
                symbol=pos.symbol,
                side=close_side,
                order_type=OrderType.MARKET,
                size=pos.size,
            )
            result = await self.exchange.place_order(order)

            pnl_pct = pos.pnl_pct(current_price)
            pnl_usd = pos.pnl_usd(current_price)

            trade_record = {
                "symbol": pos.symbol,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "exit_price": current_price,
                "size": pos.size,
                "cost_usd": pos.cost_usd,
                "pnl_pct": pnl_pct,
                "pnl_usd": pnl_usd,
                "reason": reason,
                "strategy": pos.strategy,
                "order_id": result.order_id,
                "closed_at": datetime.now(timezone.utc).isoformat(),
            }

            del self.positions[pos.symbol]
            self._closed_trades.append(trade_record)

            logger.info(
                f"Position closed [{reason}]: {pos.symbol} "
                f"PnL={pnl_pct:+.2f}% (${pnl_usd:+.2f}) order={result.order_id}"
            )
            return trade_record

        except Exception as e:
            logger.error(f"Failed to close position {pos.symbol}: {e}")
            return None

    def get_position(self, symbol: str) -> TrackedPosition | None:
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions

    @property
    def open_count(self) -> int:
        return len(self.positions)

    @property
    def closed_trades(self) -> list[dict]:
        return self._closed_trades

    def status_summary(self, prices: dict[str, float]) -> str:
        lines = []
        for symbol, pos in self.positions.items():
            price = prices.get(symbol, 0)
            pnl = pos.pnl_pct(price)
            lines.append(
                f"  {symbol}: {pos.side} {pos.size:.6f} @ ${pos.entry_price:,.2f} "
                f"→ ${price:,.2f} ({pnl:+.2f}%)"
            )
        if not lines:
            return "  No open positions"
        return "\n".join(lines)
