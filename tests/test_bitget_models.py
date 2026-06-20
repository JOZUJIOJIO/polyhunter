"""Tests for Bitget data models."""

from backend.exchanges.bitget.models import BitgetTickerData, BitgetKlineData, BitgetPositionData


class TestBitgetTickerData:
    def test_from_futures_api(self):
        raw = {
            "symbol": "BTCUSDT",
            "lastPr": "50000.5",
            "bidPr": "50000.0",
            "askPr": "50001.0",
            "high24h": "51000.0",
            "low24h": "49000.0",
            "baseVolume": "1234.5",
            "quoteVolume": "61725000.0",
            "ts": "1700000000000",
        }
        ticker = BitgetTickerData.from_api(raw)
        assert ticker.symbol == "BTCUSDT"
        assert ticker.last_price == 50000.5
        assert ticker.best_bid == 50000.0
        assert ticker.best_ask == 50001.0
        assert ticker.volume_24h == 1234.5

    def test_from_list_format(self):
        raw = [{"symbol": "ETHUSDT", "lastPr": "3000", "bidPr": "2999", "askPr": "3001",
                "high24h": "3100", "low24h": "2900", "baseVolume": "5000",
                "quoteVolume": "15000000", "ts": "1700000000000"}]
        ticker = BitgetTickerData.from_api(raw)
        assert ticker.symbol == "ETHUSDT"
        assert ticker.last_price == 3000.0


class TestBitgetKlineData:
    def test_from_api(self):
        row = ["1700000000000", "50000", "51000", "49000", "50500", "100.5"]
        kline = BitgetKlineData.from_api(row)
        assert kline.timestamp == 1700000000000
        assert kline.open == 50000.0
        assert kline.high == 51000.0
        assert kline.low == 49000.0
        assert kline.close == 50500.0
        assert kline.volume == 100.5

    def test_from_api_short_row(self):
        row = ["1700000000000", "50000", "51000", "49000", "50500"]
        kline = BitgetKlineData.from_api(row)
        assert kline.volume == 0.0


class TestBitgetPositionData:
    def test_from_api(self):
        raw = {
            "symbol": "BTCUSDT",
            "holdSide": "long",
            "total": "0.1",
            "openPriceAvg": "50000",
            "markPrice": "51000",
            "unrealizedPL": "100",
            "leverage": "10",
            "marginMode": "isolated",
        }
        pos = BitgetPositionData.from_api(raw)
        assert pos.symbol == "BTCUSDT"
        assert pos.hold_side == "long"
        assert pos.size == 0.1
        assert pos.avg_open_price == 50000.0
        assert pos.mark_price == 51000.0
        assert pos.unrealized_pnl == 100.0
        assert pos.leverage == 10
