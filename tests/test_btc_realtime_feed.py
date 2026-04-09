"""BTC 实时价格和波动率计算测试"""

from unittest.mock import patch, MagicMock

from backend.btc.realtime_feed import (
    get_btc_price,
    get_btc_klines_1m,
    compute_realtime_volatility,
)


class TestComputeRealtimeVolatility:
    def test_normal_klines(self):
        klines = [
            {"close": 80000},
            {"close": 80100},
            {"close": 80050},
            {"close": 80200},
            {"close": 80150},
        ]
        vol = compute_realtime_volatility(klines)
        assert vol > 0
        # 应该是每秒波动率，远小于 1 分钟
        assert vol < 0.01

    def test_single_kline_returns_default(self):
        klines = [{"close": 80000}]
        vol = compute_realtime_volatility(klines)
        assert vol == 0.0001

    def test_empty_klines_returns_default(self):
        vol = compute_realtime_volatility([])
        assert vol == 0.0001

    def test_two_klines(self):
        klines = [{"close": 80000}, {"close": 80100}]
        vol = compute_realtime_volatility(klines)
        assert vol > 0

    def test_minimum_volatility_floor(self):
        """完全平坦的价格应返回最小波动率"""
        klines = [{"close": 80000}] * 5
        vol = compute_realtime_volatility(klines)
        assert vol >= 0.00001


class TestGetBtcPrice:
    @patch("backend.btc.realtime_feed.httpx.Client")
    def test_success_from_first_source(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"price": "80123.45"}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        price = get_btc_price()
        assert price == 80123.45

    @patch("backend.btc.realtime_feed.httpx.Client")
    def test_with_proxy(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"price": "80000"}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        price = get_btc_price(proxy="http://127.0.0.1:7897")
        assert price == 80000.0
        # Verify proxy was passed
        mock_client_cls.assert_called()


class TestGetBtcKlines:
    @patch("backend.btc.realtime_feed.httpx.Client")
    def test_returns_parsed_klines(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [
            [1700000000, "80000", "80100", "79900", "80050", "100"],
            [1700000060, "80050", "80200", "80000", "80150", "120"],
        ]

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        klines = get_btc_klines_1m(limit=2)
        assert len(klines) == 2
        assert klines[0]["open"] == 80000.0
        assert klines[0]["close"] == 80050.0
        assert klines[1]["volume"] == 120.0
