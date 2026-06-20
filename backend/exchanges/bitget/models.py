"""Bitget-specific data models."""

from dataclasses import dataclass


@dataclass
class BitgetTickerData:
    symbol: str
    last_price: float
    best_bid: float
    best_ask: float
    high_24h: float
    low_24h: float
    volume_24h: float
    quote_volume_24h: float
    timestamp: int

    @classmethod
    def from_api(cls, data: dict) -> "BitgetTickerData":
        # Handle both list format and dict format
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        return cls(
            symbol=data.get("symbol", ""),
            last_price=float(data.get("lastPr", data.get("last", 0))),
            best_bid=float(data.get("bidPr", data.get("bestBid", 0))),
            best_ask=float(data.get("askPr", data.get("bestAsk", 0))),
            high_24h=float(data.get("high24h", 0)),
            low_24h=float(data.get("low24h", 0)),
            volume_24h=float(data.get("baseVolume", data.get("vol24h", 0))),
            quote_volume_24h=float(data.get("quoteVolume", data.get("usdtVolume", 0))),
            timestamp=int(data.get("ts", 0)),
        )


@dataclass
class BitgetKlineData:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_api(cls, row: list) -> "BitgetKlineData":
        return cls(
            timestamp=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]) if len(row) > 5 else 0.0,
        )


@dataclass
class BitgetPositionData:
    symbol: str
    hold_side: str  # "long" or "short"
    size: float
    avg_open_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int
    margin_mode: str

    @classmethod
    def from_api(cls, data: dict) -> "BitgetPositionData":
        return cls(
            symbol=data.get("symbol", ""),
            hold_side=data.get("holdSide", ""),
            size=float(data.get("total", data.get("size", 0))),
            avg_open_price=float(data.get("openPriceAvg", data.get("averageOpenPrice", 0))),
            mark_price=float(data.get("markPrice", 0)),
            unrealized_pnl=float(data.get("unrealizedPL", data.get("unrealisedPL", 0))),
            leverage=int(data.get("leverage", 1)),
            margin_mode=data.get("marginMode", "isolated"),
        )
