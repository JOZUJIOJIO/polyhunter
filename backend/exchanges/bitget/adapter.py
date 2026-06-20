"""Bitget ExchangeAdapter implementation."""

import logging

from backend.config import Settings
from backend.exchanges.base import (
    ExchangeAdapter,
    ExchangePosition,
    Kline,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    PriceCallback,
    Ticker,
)
from backend.exchanges.bitget.client import BitgetClient
from backend.exchanges.bitget.models import BitgetKlineData, BitgetPositionData, BitgetTickerData
from backend.exchanges.bitget.websocket import BitgetWebSocket

logger = logging.getLogger(__name__)


class BitgetAdapter(ExchangeAdapter):
    """Bitget exchange adapter supporting spot and USDT-M futures."""

    name = "bitget"

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self._account_type = self.settings.BITGET_ACCOUNT_TYPE  # "spot" or "futures"
        self._client = BitgetClient(
            api_key=self.settings.BITGET_API_KEY,
            secret_key=self.settings.BITGET_SECRET_KEY,
            passphrase=self.settings.BITGET_PASSPHRASE,
        )
        inst_type = "USDT-FUTURES" if self.is_futures else "SPOT"
        self._ws = BitgetWebSocket(inst_type=inst_type)
        self._ws_connected = False

    @property
    def is_futures(self) -> bool:
        return self._account_type == "futures"

    async def get_ticker(self, symbol: str) -> Ticker:
        if self.is_futures:
            raw = await self._client.get_ticker(symbol)
        else:
            raw = await self._client.get_spot_ticker(symbol)

        data = BitgetTickerData.from_api(raw)
        return Ticker(
            symbol=data.symbol,
            last_price=data.last_price,
            bid=data.best_bid,
            ask=data.best_ask,
            high_24h=data.high_24h,
            low_24h=data.low_24h,
            volume_24h=data.volume_24h,
            timestamp=data.timestamp / 1000.0,
        )

    async def get_klines(
        self, symbol: str, interval: str = "5m", limit: int = 100
    ) -> list[Kline]:
        if self.is_futures:
            raw = await self._client.get_klines(symbol, interval, limit)
        else:
            # Spot uses different interval format: "5min" instead of "5m"
            spot_interval = interval.replace("m", "min") if interval.endswith("m") else interval
            raw = await self._client.get_spot_klines(symbol, spot_interval, limit)

        klines = []
        for row in raw:
            if isinstance(row, list):
                k = BitgetKlineData.from_api(row)
                klines.append(Kline(
                    timestamp=k.timestamp / 1000.0,
                    open=k.open,
                    high=k.high,
                    low=k.low,
                    close=k.close,
                    volume=k.volume,
                ))
        return klines

    # Minimum order sizes and precision per symbol (Bitget USDT-FUTURES)
    _CONTRACT_SPECS = {
        "BTCUSDT": {"min_size": 0.001, "step": 0.001, "decimals": 3},
        "ETHUSDT": {"min_size": 0.01, "step": 0.01, "decimals": 2},
        "default": {"min_size": 0.01, "step": 0.01, "decimals": 2},
    }

    def _round_size(self, symbol: str, size: float) -> float:
        spec = self._CONTRACT_SPECS.get(symbol, self._CONTRACT_SPECS["default"])
        # Round down to step precision
        import math
        rounded = math.floor(size / spec["step"]) * spec["step"]
        rounded = round(rounded, spec["decimals"])
        return max(rounded, spec["min_size"])

    async def place_order(self, order: OrderRequest) -> OrderResult:
        side_str = "buy" if order.side == OrderSide.BUY else "sell"
        type_str = "market" if order.order_type == OrderType.MARKET else "limit"
        price_str = str(order.price) if order.price else None

        # For futures, adjust size to meet minimum and precision requirements
        adjusted_size = order.size
        if self.is_futures:
            adjusted_size = self._round_size(order.symbol, order.size)
            logger.info(f"Order size: {order.size} → adjusted to {adjusted_size} for {order.symbol}")

        size_str = str(adjusted_size)

        if self.is_futures:
            trade_side = "open"  # open position by default
            raw = await self._client.place_futures_order(
                symbol=order.symbol,
                side=side_str,
                order_type=type_str,
                size=size_str,
                price=price_str,
                trade_side=trade_side,
            )
        else:
            raw = await self._client.place_spot_order(
                symbol=order.symbol,
                side=side_str,
                order_type=type_str,
                size=size_str,
                price=price_str,
            )

        order_id = raw.get("orderId", raw.get("data", {}).get("orderId", "unknown"))
        logger.info(
            f"Bitget order placed: {order.side.value} {order.size} {order.symbol} "
            f"@ {order.price or 'MARKET'} → {order_id}"
        )

        return OrderResult(
            order_id=str(order_id),
            symbol=order.symbol,
            side=order.side,
            price=order.price or 0.0,
            size=order.size,
            filled_size=order.size,  # Assume filled for market orders
            status=OrderStatus.FILLED if order.order_type == OrderType.MARKET else OrderStatus.PENDING,
            raw=raw,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            if self.is_futures:
                await self._client.cancel_futures_order(symbol, order_id)
            else:
                await self._client.cancel_spot_order(symbol, order_id)
            return True
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    async def get_balance(self) -> dict[str, float]:
        if self.is_futures:
            raw = await self._client.get_account_balance()
            balances = {}
            if isinstance(raw, list):
                for acc in raw:
                    coin = acc.get("marginCoin", "USDT")
                    available = float(acc.get("available", 0))
                    balances[coin] = available
            return balances
        else:
            raw = await self._client.get_spot_balance()
            balances = {}
            if isinstance(raw, list):
                for item in raw:
                    coin = item.get("coin", "")
                    available = float(item.get("available", 0))
                    if available > 0:
                        balances[coin] = available
            return balances

    async def get_positions(self) -> list[ExchangePosition]:
        if not self.is_futures:
            return []  # Spot doesn't have positions in the futures sense

        raw = await self._client.get_futures_positions()
        positions = []
        for item in raw:
            p = BitgetPositionData.from_api(item)
            if p.size > 0:
                positions.append(ExchangePosition(
                    symbol=p.symbol,
                    side="long" if p.hold_side == "long" else "short",
                    size=p.size,
                    avg_entry_price=p.avg_open_price,
                    current_price=p.mark_price,
                    unrealized_pnl=p.unrealized_pnl,
                    leverage=p.leverage,
                ))
        return positions

    async def subscribe_price(self, symbol: str, callback: PriceCallback) -> None:
        if not self._ws_connected:
            await self._ws.connect()
            self._ws_connected = True

        async def _on_ticker(data_list: list):
            for item in data_list:
                price = float(item.get("lastPr", item.get("last", 0)))
                ts = float(item.get("ts", 0)) / 1000.0
                await callback(symbol, price, ts)

        await self._ws.subscribe_ticker(symbol, _on_ticker)

    async def unsubscribe_price(self, symbol: str) -> None:
        await self._ws.unsubscribe(symbol)

    async def set_leverage(self, symbol: str, leverage: int) -> None:
        if self.is_futures:
            await self._client.set_leverage(symbol, leverage, hold_side="long")
            await self._client.set_leverage(symbol, leverage, hold_side="short")
            logger.info(f"Set leverage for {symbol} to {leverage}x")

    async def close(self) -> None:
        await self._ws.close()
        await self._client.close()
