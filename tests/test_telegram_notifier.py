"""Tests for Telegram notification system."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch

from backend.config import Settings
from backend.notify.telegram import TelegramNotifier


@pytest.fixture
def notifier():
    settings = Settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_CHAT_ID="12345")
    return TelegramNotifier(settings)


@pytest.fixture
def disabled_notifier():
    settings = Settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
    return TelegramNotifier(settings)


class TestTelegramNotifier:
    def test_enabled_when_configured(self, notifier):
        assert notifier.enabled is True

    def test_disabled_when_not_configured(self, disabled_notifier):
        assert disabled_notifier.enabled is False

    @pytest.mark.asyncio
    async def test_send_disabled_returns_false(self, disabled_notifier):
        result = await disabled_notifier.send("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self, notifier):
        mock_response = httpx.Response(200, json={"ok": True, "result": {}})
        with patch.object(notifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await notifier.send("Hello!")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self, notifier):
        mock_response = httpx.Response(200, json={"ok": False, "description": "Bad request"})
        with patch.object(notifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await notifier.send("Hello!")
            assert result is False

    @pytest.mark.asyncio
    async def test_notify_signal(self, notifier):
        mock_response = httpx.Response(200, json={"ok": True, "result": {}})
        with patch.object(notifier._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await notifier.notify_signal(
                exchange="Bitget",
                symbol="BTCUSDT",
                signal_type="EMA_CROSSOVER",
                side="BUY",
                price=50000.0,
                edge_pct=1.5,
                confidence=75,
                reason="EMA9 crossed above EMA21",
            )
            assert result is True
            call_args = mock_post.call_args
            body = call_args[1]["json"]
            assert "BTCUSDT" in body["text"]
            assert "BUY" in body["text"]

    @pytest.mark.asyncio
    async def test_notify_order(self, notifier):
        mock_response = httpx.Response(200, json={"ok": True, "result": {}})
        with patch.object(notifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await notifier.notify_order(
                exchange="Bitget",
                symbol="BTCUSDT",
                side="BUY",
                order_type="MARKET",
                price=50000.0,
                size=0.001,
                order_id="abc123",
                status="FILLED",
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_notify_circuit_breaker(self, notifier):
        mock_response = httpx.Response(200, json={"ok": True, "result": {}})
        with patch.object(notifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await notifier.notify_circuit_breaker(
                exchange="Bitget",
                consecutive_losses=5,
                total_loss=-250.0,
                cooldown_min=60,
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_notify_daily_summary(self, notifier):
        mock_response = httpx.Response(200, json={"ok": True, "result": {}})
        with patch.object(notifier._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await notifier.notify_daily_summary(
                exchange="Bitget",
                total_trades=10,
                wins=7,
                losses=3,
                total_pnl=150.0,
                balance=1000.0,
            )
            assert result is True
