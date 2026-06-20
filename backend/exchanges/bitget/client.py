"""Bitget REST API client with HMAC-SHA256 authentication."""

import base64
import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.bitget.com"


class BitgetClient:
    """Low-level Bitget REST API client."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        passphrase: str,
        base_url: str = BASE_URL,
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = timestamp + method.upper() + path + body
        mac = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        )
        return base64.b64encode(mac.digest()).decode("utf-8")

    def _headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        sign = self._sign(timestamp, method, path, body)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "locale": "en-US",
        }

    async def _request(
        self, method: str, path: str, params: dict | None = None, body: dict | None = None
    ) -> dict[str, Any]:
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)

        full_path = path + query
        body_str = ""
        if body:
            import json
            body_str = json.dumps(body)

        headers = self._headers(method, full_path, body_str)

        resp = await self._client.request(
            method,
            full_path,
            content=body_str if body_str else None,
            headers=headers,
        )

        data = resp.json()
        if data.get("code") != "00000":
            logger.error(f"Bitget API error: {data}")
            raise BitgetAPIError(data.get("code", ""), data.get("msg", "Unknown error"))
        return data.get("data", data)

    # ── Market Data ──

    async def get_ticker(self, symbol: str, product_type: str = "USDT-FUTURES") -> dict:
        return await self._request(
            "GET",
            f"/api/v2/mix/market/ticker",
            params={"symbol": symbol, "productType": product_type},
        )

    async def get_klines(
        self,
        symbol: str,
        granularity: str = "5m",
        limit: int = 100,
        product_type: str = "USDT-FUTURES",
    ) -> list:
        data = await self._request(
            "GET",
            f"/api/v2/mix/market/candles",
            params={
                "symbol": symbol,
                "productType": product_type,
                "granularity": granularity,
                "limit": str(limit),
            },
        )
        return data if isinstance(data, list) else []

    async def get_orderbook(
        self, symbol: str, limit: int = 15, product_type: str = "USDT-FUTURES"
    ) -> dict:
        return await self._request(
            "GET",
            f"/api/v2/mix/market/depth",
            params={
                "symbol": symbol,
                "productType": product_type,
                "limit": str(limit),
            },
        )

    # ── Spot Market Data ──

    async def get_spot_ticker(self, symbol: str) -> dict:
        return await self._request(
            "GET",
            "/api/v2/spot/market/tickers",
            params={"symbol": symbol},
        )

    async def get_spot_klines(
        self, symbol: str, granularity: str = "5min", limit: int = 100
    ) -> list:
        data = await self._request(
            "GET",
            "/api/v2/spot/market/candles",
            params={"symbol": symbol, "granularity": granularity, "limit": str(limit)},
        )
        return data if isinstance(data, list) else []

    # ── Account ──

    async def get_account_balance(self, product_type: str = "USDT-FUTURES") -> dict:
        return await self._request(
            "GET",
            f"/api/v2/mix/account/accounts",
            params={"productType": product_type},
        )

    async def get_spot_balance(self) -> dict:
        return await self._request("GET", "/api/v2/spot/account/assets")

    # ── Trading (Futures) ──

    async def place_futures_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        size: str,
        price: str | None = None,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        trade_side: str = "open",
    ) -> dict:
        body: dict[str, Any] = {
            "symbol": symbol,
            "productType": product_type,
            "marginMode": "isolated",
            "marginCoin": margin_coin,
            "size": size,
            "side": side.lower(),
            "tradeSide": trade_side,
            "orderType": order_type.lower(),
        }
        if price and order_type.upper() == "LIMIT":
            body["price"] = price
        return await self._request("POST", "/api/v2/mix/order/place-order", body=body)

    async def cancel_futures_order(
        self, symbol: str, order_id: str, product_type: str = "USDT-FUTURES"
    ) -> dict:
        return await self._request(
            "POST",
            "/api/v2/mix/order/cancel-order",
            body={
                "symbol": symbol,
                "productType": product_type,
                "orderId": order_id,
            },
        )

    async def get_futures_positions(self, product_type: str = "USDT-FUTURES") -> list:
        data = await self._request(
            "GET",
            "/api/v2/mix/position/all-position",
            params={"productType": product_type},
        )
        return data if isinstance(data, list) else []

    # ── Trading (Spot) ──

    async def place_spot_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        size: str,
        price: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {
            "symbol": symbol,
            "side": side.lower(),
            "orderType": order_type.lower(),
            "size": size,
            "force": "gtc",
        }
        if price and order_type.upper() == "LIMIT":
            body["price"] = price
        return await self._request("POST", "/api/v2/spot/trade/place-order", body=body)

    async def cancel_spot_order(self, symbol: str, order_id: str) -> dict:
        return await self._request(
            "POST",
            "/api/v2/spot/trade/cancel-order",
            body={"symbol": symbol, "orderId": order_id},
        )

    # ── Leverage ──

    async def set_leverage(
        self,
        symbol: str,
        leverage: int,
        margin_coin: str = "USDT",
        product_type: str = "USDT-FUTURES",
        hold_side: str = "long",
    ) -> dict:
        return await self._request(
            "POST",
            "/api/v2/mix/account/set-leverage",
            body={
                "symbol": symbol,
                "productType": product_type,
                "marginCoin": margin_coin,
                "leverage": str(leverage),
                "holdSide": hold_side,
            },
        )

    async def close(self):
        await self._client.aclose()


class BitgetAPIError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Bitget API Error [{code}]: {message}")
