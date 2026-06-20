"""Telegram notification system for trading events."""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send trading notifications via Telegram Bot API."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.bot_token = self.settings.TELEGRAM_BOT_TOKEN
        self.chat_id = self.settings.TELEGRAM_CHAT_ID
        self._client = httpx.AsyncClient(timeout=10.0)
        self._enabled = bool(self.bot_token and self.chat_id)

        if not self._enabled:
            logger.warning("Telegram notifications disabled: missing BOT_TOKEN or CHAT_ID")

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, message: str, parse_mode: str = "HTML") -> bool:
        if not self._enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }

        try:
            resp = await self._client.post(url, json=payload)
            data = resp.json()
            if not data.get("ok"):
                logger.error(f"Telegram send failed: {data}")
                return False
            return True
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    # ── Formatted Notifications ──

    async def notify_signal(
        self,
        exchange: str,
        symbol: str,
        signal_type: str,
        side: str,
        price: float,
        edge_pct: float,
        confidence: int,
        reason: str = "",
    ) -> bool:
        emoji = "\U0001f7e2" if side.upper() == "BUY" else "\U0001f534"
        msg = (
            f"{emoji} <b>Signal Detected</b>\n"
            f"\U0001f3e6 Exchange: {exchange}\n"
            f"\U0001f4b1 Symbol: <code>{symbol}</code>\n"
            f"\U0001f4ca Type: {signal_type}\n"
            f"\U0001f449 Side: <b>{side.upper()}</b>\n"
            f"\U0001f4b0 Price: ${price:,.2f}\n"
            f"\U0001f4c8 Edge: {edge_pct:.1f}%\n"
            f"\U0001f3af Confidence: {confidence}%\n"
        )
        if reason:
            msg += f"\U0001f4dd Reason: {reason}\n"
        msg += f"\U0001f552 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        return await self.send(msg)

    async def notify_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        order_type: str,
        price: float,
        size: float,
        order_id: str,
        status: str,
    ) -> bool:
        emoji = "\u2705" if status == "FILLED" else "\u274c" if status == "CANCELLED" else "\u23f3"
        msg = (
            f"{emoji} <b>Order {status}</b>\n"
            f"\U0001f3e6 Exchange: {exchange}\n"
            f"\U0001f4b1 Symbol: <code>{symbol}</code>\n"
            f"\U0001f449 {side.upper()} {order_type}\n"
            f"\U0001f4b0 Price: ${price:,.2f}\n"
            f"\U0001f4e6 Size: {size}\n"
            f"\U0001f194 Order ID: <code>{order_id[:16]}</code>\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        )
        return await self.send(msg)

    async def notify_position_closed(
        self,
        exchange: str,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        size: float,
        pnl: float,
    ) -> bool:
        emoji = "\U0001f4b5" if pnl > 0 else "\U0001f4b8"
        pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        if side.upper() == "SELL":
            pnl_pct = -pnl_pct
        msg = (
            f"{emoji} <b>Position Closed</b>\n"
            f"\U0001f3e6 Exchange: {exchange}\n"
            f"\U0001f4b1 Symbol: <code>{symbol}</code>\n"
            f"\U0001f449 Side: {side.upper()}\n"
            f"\U0001f4c8 Entry: ${entry_price:,.2f}\n"
            f"\U0001f4c9 Exit: ${exit_price:,.2f}\n"
            f"\U0001f4e6 Size: {size}\n"
            f"\U0001f4b0 PnL: <b>${pnl:+,.2f}</b> ({pnl_pct:+.2f}%)\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        )
        return await self.send(msg)

    async def notify_circuit_breaker(
        self, exchange: str, consecutive_losses: int, total_loss: float, cooldown_min: int
    ) -> bool:
        msg = (
            f"\u26a0\ufe0f <b>Circuit Breaker Triggered!</b>\n"
            f"\U0001f3e6 Exchange: {exchange}\n"
            f"\U0001f534 Consecutive Losses: {consecutive_losses}\n"
            f"\U0001f4b8 Total Loss: ${abs(total_loss):,.2f}\n"
            f"\u23f0 Cooldown: {cooldown_min} minutes\n"
            f"\U0001f6d1 Trading is paused.\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        )
        return await self.send(msg)

    async def notify_daily_summary(
        self,
        exchange: str,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
        balance: float,
    ) -> bool:
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        emoji = "\U0001f4c8" if total_pnl >= 0 else "\U0001f4c9"
        msg = (
            f"\U0001f4ca <b>Daily Summary — {exchange}</b>\n"
            f"\U0001f4c5 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            f"{'='*24}\n"
            f"\U0001f4b1 Trades: {total_trades}\n"
            f"\u2705 Wins: {wins} | \u274c Losses: {losses}\n"
            f"\U0001f3af Win Rate: {win_rate:.1f}%\n"
            f"{emoji} PnL: <b>${total_pnl:+,.2f}</b>\n"
            f"\U0001f4b0 Balance: ${balance:,.2f}\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        )
        return await self.send(msg)

    async def notify_price_alert(
        self, exchange: str, symbol: str, price: float, change_pct: float, alert_type: str
    ) -> bool:
        emoji = "\U0001f4c8" if change_pct > 0 else "\U0001f4c9"
        msg = (
            f"\U0001f514 <b>Price Alert — {alert_type}</b>\n"
            f"\U0001f3e6 Exchange: {exchange}\n"
            f"\U0001f4b1 Symbol: <code>{symbol}</code>\n"
            f"\U0001f4b0 Price: ${price:,.2f}\n"
            f"{emoji} Change: {change_pct:+.2f}%\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        )
        return await self.send(msg)

    async def notify_error(self, exchange: str, error: str, context: str = "") -> bool:
        msg = (
            f"\U0001f6a8 <b>System Error</b>\n"
            f"\U0001f3e6 Exchange: {exchange}\n"
            f"\u274c Error: {error}\n"
        )
        if context:
            msg += f"\U0001f4dd Context: {context}\n"
        msg += f"\U0001f552 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        return await self.send(msg)

    async def close(self):
        await self._client.aclose()
