"""BTC 5分钟市场发现测试"""

import time
from unittest.mock import patch, MagicMock
import json

from backend.btc.market_finder import (
    get_current_window_ts,
    get_next_window_ts,
    make_slug,
    find_current_5m_market,
)


class TestWindowTimestamp:
    def test_current_window_aligned_to_5min(self):
        ts = get_current_window_ts()
        assert ts % 300 == 0

    def test_next_window_is_300s_later(self):
        current = get_current_window_ts()
        nxt = get_next_window_ts()
        assert nxt == current + 300

    def test_current_window_not_in_future(self):
        ts = get_current_window_ts()
        assert ts <= int(time.time())


class TestMakeSlug:
    def test_btc_slug_format(self):
        slug = make_slug(1700000000)
        assert slug == "btc-updown-5m-1700000000"

    def test_custom_coin(self):
        slug = make_slug(1700000000, coin="eth")
        assert slug == "eth-updown-5m-1700000000"


class TestFindCurrent5mMarket:
    @patch("backend.btc.market_finder._get_clob_prices")
    @patch("backend.btc.market_finder._fetch_market_by_slug")
    def test_finds_market_successfully(self, mock_fetch, mock_prices):
        mock_fetch.return_value = {
            "market_id": "0xabc123",
            "condition_id": "0xcond",
            "question": "BTC Up or Down 5M",
            "token_yes": "token_yes_id",
            "token_no": "token_no_id",
            "liquidity": 5000.0,
        }
        mock_prices.return_value = (0.55, 0.45)

        result = find_current_5m_market()
        assert result is not None
        assert result["token_yes"] == "token_yes_id"
        assert result["token_no"] == "token_no_id"
        assert result["yes_price"] == 0.55
        assert result["no_price"] == 0.45
        assert result["seconds_left"] > 0
        assert "slug" in result

    @patch("backend.btc.market_finder._fetch_market_by_slug")
    def test_returns_none_when_no_market(self, mock_fetch):
        mock_fetch.return_value = None
        result = find_current_5m_market()
        assert result is None

    @patch("backend.btc.market_finder._get_clob_prices")
    @patch("backend.btc.market_finder._fetch_market_by_slug")
    def test_falls_back_to_next_window(self, mock_fetch, mock_prices):
        """当前窗口没市场时尝试下一个窗口"""
        # 第一次调用返回 None，第二次返回市场
        mock_fetch.side_effect = [None, {
            "market_id": "0xnext",
            "condition_id": "",
            "question": "BTC Next",
            "token_yes": "ty",
            "token_no": "tn",
            "liquidity": 3000.0,
        }]
        mock_prices.return_value = (0.50, 0.50)

        result = find_current_5m_market()
        assert result is not None
        assert result["market_id"] == "0xnext"


class TestFetchMarketBySlug:
    @patch("backend.btc.market_finder.httpx.Client")
    def test_parses_gamma_response(self, mock_client_cls):
        from backend.btc.market_finder import _fetch_market_by_slug

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{
            "id": "market123",
            "conditionId": "cond456",
            "question": "BTC Up?",
            "clobTokenIds": json.dumps(["token_a", "token_b"]),
            "liquidityClob": "4500",
        }]

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = _fetch_market_by_slug("btc-updown-5m-1700000000")
        assert result["market_id"] == "market123"
        assert result["token_yes"] == "token_a"
        assert result["token_no"] == "token_b"
        assert result["liquidity"] == 4500.0

    @patch("backend.btc.market_finder.httpx.Client")
    def test_returns_none_for_empty_response(self, mock_client_cls):
        from backend.btc.market_finder import _fetch_market_by_slug

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = []

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = _fetch_market_by_slug("nonexistent-slug")
        assert result is None
