"""Bitget WebSocket client for real-time market data."""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

WS_URL = "wss://ws.bitget.com/v2/ws/public"


class BitgetWebSocket:
    """WebSocket client for Bitget real-time price feeds."""

    def __init__(self, inst_type: str = "SPOT"):
        self._ws = None
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._inst_type = inst_type  # "SPOT" or "USDT-FUTURES"

    async def connect(self):
        try:
            import websockets
        except ImportError:
            raise ImportError("Install websockets: pip install websockets")

        self._ws = await websockets.connect(WS_URL, ping_interval=20, ping_timeout=10)
        self._running = True
        self._task = asyncio.create_task(self._listen())
        self._ping_task = asyncio.create_task(self._keep_alive())
        logger.info("Bitget WebSocket connected")

    async def subscribe_ticker(self, symbol: str, callback: Callable) -> None:
        channel_key = f"ticker:{symbol}"
        if channel_key not in self._callbacks:
            self._callbacks[channel_key] = []
        self._callbacks[channel_key].append(callback)

        msg = {
            "op": "subscribe",
            "args": [
                {
                    "instType": self._inst_type,
                    "channel": "ticker",
                    "instId": symbol,
                }
            ],
        }
        if self._ws:
            await self._ws.send(json.dumps(msg))
            logger.info(f"Subscribed to ticker: {symbol}")

    async def subscribe_kline(
        self, symbol: str, interval: str, callback: Callable
    ) -> None:
        channel_key = f"candle{interval}:{symbol}"
        if channel_key not in self._callbacks:
            self._callbacks[channel_key] = []
        self._callbacks[channel_key].append(callback)

        msg = {
            "op": "subscribe",
            "args": [
                {
                    "instType": self._inst_type,
                    "channel": f"candle{interval}",
                    "instId": symbol,
                }
            ],
        }
        if self._ws:
            await self._ws.send(json.dumps(msg))
            logger.info(f"Subscribed to kline {interval}: {symbol}")

    async def unsubscribe(self, symbol: str) -> None:
        keys_to_remove = [k for k in self._callbacks if k.endswith(f":{symbol}")]
        for key in keys_to_remove:
            channel_type = key.split(":")[0]
            msg = {
                "op": "unsubscribe",
                "args": [
                    {
                        "instType": self._inst_type,
                        "channel": channel_type,
                        "instId": symbol,
                    }
                ],
            }
            if self._ws:
                await self._ws.send(json.dumps(msg))
            del self._callbacks[key]
        logger.info(f"Unsubscribed from {symbol}")

    async def _listen(self):
        while self._running and self._ws:
            try:
                raw = await self._ws.recv()

                # Bitget sends "pong" as plain text response to "ping"
                if isinstance(raw, str) and raw.strip() in ("pong", ""):
                    continue

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if "action" in data and data["action"] == "snapshot" or data.get("action") == "update":
                    arg = data.get("arg", {})
                    channel = arg.get("channel", "")
                    inst_id = arg.get("instId", "")
                    channel_key = f"{channel}:{inst_id}"

                    callbacks = self._callbacks.get(channel_key, [])
                    for cb in callbacks:
                        try:
                            result = cb(data.get("data", []))
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.error(f"Callback error for {channel_key}: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.error(f"WebSocket listen error: {e}")
                    await asyncio.sleep(5)
                    await self._reconnect()

    async def _keep_alive(self):
        while self._running:
            try:
                await asyncio.sleep(25)
                if self._ws:
                    await self._ws.send("ping")
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _reconnect(self):
        logger.info("Attempting WebSocket reconnect...")
        try:
            if self._ws:
                await self._ws.close()
        except Exception:
            pass

        try:
            import websockets
            self._ws = await websockets.connect(WS_URL, ping_interval=20, ping_timeout=10)
            # Re-subscribe all channels
            for key in self._callbacks:
                parts = key.split(":")
                channel = parts[0]
                inst_id = parts[1]
                msg = {
                    "op": "subscribe",
                    "args": [
                        {
                            "instType": self._inst_type,
                            "channel": channel,
                            "instId": inst_id,
                        }
                    ],
                }
                await self._ws.send(json.dumps(msg))
            logger.info("WebSocket reconnected and resubscribed")
        except Exception as e:
            logger.error(f"Reconnect failed: {e}")

    async def close(self):
        self._running = False
        if self._ping_task:
            self._ping_task.cancel()
        if self._task:
            self._task.cancel()
        if self._ws:
            await self._ws.close()
        logger.info("Bitget WebSocket closed")
