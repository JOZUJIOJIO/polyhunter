"""Tests for exchange base types."""

from backend.exchanges.base import (
    OrderSide,
    OrderType,
    OrderStatus,
    Ticker,
    Kline,
    OrderRequest,
    OrderResult,
    ExchangePosition,
)


class TestOrderSide:
    def test_values(self):
        assert OrderSide.BUY == "BUY"
        assert OrderSide.SELL == "SELL"


class TestOrderType:
    def test_values(self):
        assert OrderType.MARKET == "MARKET"
        assert OrderType.LIMIT == "LIMIT"


class TestTicker:
    def test_creation(self):
        t = Ticker(
            symbol="BTCUSDT",
            last_price=50000.0,
            bid=49999.0,
            ask=50001.0,
            high_24h=51000.0,
            low_24h=49000.0,
            volume_24h=1000.0,
            timestamp=1700000000.0,
        )
        assert t.symbol == "BTCUSDT"
        assert t.last_price == 50000.0


class TestOrderRequest:
    def test_market_order(self):
        req = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            size=0.001,
        )
        assert req.price is None

    def test_limit_order(self):
        req = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            size=1.0,
            price=3000.0,
        )
        assert req.price == 3000.0


class TestExchangePosition:
    def test_defaults(self):
        pos = ExchangePosition(
            symbol="BTCUSDT",
            side="long",
            size=0.1,
            avg_entry_price=50000.0,
            current_price=51000.0,
            unrealized_pnl=100.0,
        )
        assert pos.leverage == 1
