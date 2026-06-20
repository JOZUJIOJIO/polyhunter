"""Tests for position manager with stop-loss and take-profit."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.config import Settings
from backend.exchanges.base import OrderResult, OrderSide, OrderStatus
from backend.trader.position_manager import PositionManager, TrackedPosition


@pytest.fixture
def mock_exchange():
    exchange = AsyncMock()
    exchange.name = "bitget"
    exchange.place_order = AsyncMock(return_value=OrderResult(
        order_id="close-123",
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        price=50000,
        size=0.001,
        filled_size=0.001,
        status=OrderStatus.FILLED,
    ))
    return exchange


@pytest.fixture
def manager(mock_exchange):
    settings = Settings(BITGET_STOP_LOSS_PCT=5.0, BITGET_TAKE_PROFIT_PCT=10.0)
    return PositionManager(mock_exchange, settings)


class TestTrackedPosition:
    def test_pnl_pct_profit(self):
        pos = TrackedPosition(symbol="BTC", side="BUY", entry_price=100, size=1, cost_usd=100)
        assert pos.pnl_pct(110) == pytest.approx(10.0)

    def test_pnl_pct_loss(self):
        pos = TrackedPosition(symbol="BTC", side="BUY", entry_price=100, size=1, cost_usd=100)
        assert pos.pnl_pct(95) == pytest.approx(-5.0)

    def test_pnl_usd_profit(self):
        pos = TrackedPosition(symbol="BTC", side="BUY", entry_price=50000, size=0.1, cost_usd=5000)
        assert pos.pnl_usd(55000) == pytest.approx(500.0)

    def test_pnl_usd_loss(self):
        pos = TrackedPosition(symbol="BTC", side="BUY", entry_price=50000, size=0.1, cost_usd=5000)
        assert pos.pnl_usd(47500) == pytest.approx(-250.0)

    def test_zero_entry_price(self):
        pos = TrackedPosition(symbol="BTC", side="BUY", entry_price=0, size=1, cost_usd=0)
        assert pos.pnl_pct(100) == 0.0


class TestPositionManager:
    def test_open_position(self, manager):
        pos = manager.open_position("BTCUSDT", "BUY", 50000, 0.001, 50)
        assert pos.symbol == "BTCUSDT"
        assert manager.has_position("BTCUSDT")
        assert manager.open_count == 1

    def test_no_position(self, manager):
        assert not manager.has_position("BTCUSDT")
        assert manager.open_count == 0

    @pytest.mark.asyncio
    async def test_stop_loss_triggers(self, manager, mock_exchange):
        manager.open_position("BTCUSDT", "BUY", 50000, 0.001, 50)

        # Price drops 6% → should trigger SL (threshold 5%)
        closed = await manager.check_positions({"BTCUSDT": 47000})

        assert len(closed) == 1
        assert closed[0]["reason"] == "STOP_LOSS"
        assert closed[0]["pnl_pct"] == pytest.approx(-6.0)
        assert not manager.has_position("BTCUSDT")
        mock_exchange.place_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_take_profit_triggers(self, manager, mock_exchange):
        manager.open_position("BTCUSDT", "BUY", 50000, 0.001, 50)

        # Price rises 12% → should trigger TP (threshold 10%)
        closed = await manager.check_positions({"BTCUSDT": 56000})

        assert len(closed) == 1
        assert closed[0]["reason"] == "TAKE_PROFIT"
        assert closed[0]["pnl_pct"] == pytest.approx(12.0)
        assert not manager.has_position("BTCUSDT")

    @pytest.mark.asyncio
    async def test_no_trigger_within_range(self, manager, mock_exchange):
        manager.open_position("BTCUSDT", "BUY", 50000, 0.001, 50)

        # Price moves 3% up → no trigger
        closed = await manager.check_positions({"BTCUSDT": 51500})

        assert len(closed) == 0
        assert manager.has_position("BTCUSDT")
        mock_exchange.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_positions(self, manager, mock_exchange):
        manager.open_position("BTCUSDT", "BUY", 50000, 0.001, 50)
        manager.open_position("ETHUSDT", "BUY", 2000, 0.5, 1000)

        assert manager.open_count == 2

        # BTC hits TP, ETH stays in range
        closed = await manager.check_positions({"BTCUSDT": 56000, "ETHUSDT": 2050})

        assert len(closed) == 1
        assert closed[0]["symbol"] == "BTCUSDT"
        assert manager.open_count == 1
        assert manager.has_position("ETHUSDT")

    @pytest.mark.asyncio
    async def test_close_failure_keeps_position(self, manager, mock_exchange):
        mock_exchange.place_order.side_effect = Exception("API error")
        manager.open_position("BTCUSDT", "BUY", 50000, 0.001, 50)

        closed = await manager.check_positions({"BTCUSDT": 47000})

        assert len(closed) == 0
        assert manager.has_position("BTCUSDT")  # Still tracked

    def test_status_summary(self, manager):
        manager.open_position("BTCUSDT", "BUY", 50000, 0.001, 50)
        summary = manager.status_summary({"BTCUSDT": 51000})
        assert "BTCUSDT" in summary
        assert "BUY" in summary
        assert "+2.00%" in summary

    def test_status_summary_empty(self, manager):
        summary = manager.status_summary({})
        assert "No open positions" in summary
