"""Unified exchange adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Coroutine


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Ticker:
    symbol: str
    last_price: float
    bid: float
    ask: float
    high_24h: float
    low_24h: float
    volume_24h: float
    timestamp: float


@dataclass
class Kline:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType
    size: float
    price: float | None = None  # None for market orders


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    size: float
    filled_size: float
    status: OrderStatus
    raw: dict = field(default_factory=dict)


@dataclass
class ExchangePosition:
    symbol: str
    side: str
    size: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: int = 1


PriceCallback = Callable[[str, float, float], Coroutine[Any, Any, None]]
# callback(symbol, price, timestamp)


class ExchangeAdapter(ABC):
    """Unified interface for all exchanges."""

    name: str = "base"

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        ...

    @abstractmethod
    async def get_klines(
        self, symbol: str, interval: str = "5m", limit: int = 100
    ) -> list[Kline]:
        ...

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResult:
        ...

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        ...

    @abstractmethod
    async def get_balance(self) -> dict[str, float]:
        ...

    @abstractmethod
    async def get_positions(self) -> list[ExchangePosition]:
        ...

    @abstractmethod
    async def subscribe_price(self, symbol: str, callback: PriceCallback) -> None:
        ...

    @abstractmethod
    async def unsubscribe_price(self, symbol: str) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
