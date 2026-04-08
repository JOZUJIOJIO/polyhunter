import logging
import os

import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.db.models import Signal, Trade
from backend.trader.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(self, session: Session, risk_manager: RiskManager, settings: Settings | None = None):
        self.session = session
        self.risk_manager = risk_manager
        self.settings = settings or Settings()
        self._clob_client: ClobClient | None = None

    def execute(self, signal_id: int | None, market_id: str, token_id: str, side: str, price: float, size: float) -> Trade | None:
        cost = size * price
        check = self.risk_manager.check_order(market_id=market_id, side=side, size=size, price=price)
        if not check.approved:
            logger.warning(f"Order rejected by risk manager: {check.reason}")
            return None

        trade = Trade(signal_id=signal_id, market_id=market_id, token_id=token_id, side=side, price=price, size=size, cost=cost, status="PENDING")
        self.session.add(trade)
        self.session.commit()

        try:
            order_id = self._submit_order(token_id, side, price, size)
            trade.status = "FILLED"
            trade.order_id = order_id
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            trade.status = "CANCELLED"

        if signal_id:
            signal = self.session.get(Signal, signal_id)
            if signal:
                signal.status = "ACTED"

        self.session.commit()
        return trade

    def _get_clob_client(self) -> ClobClient:
        if self._clob_client:
            return self._clob_client

        # 注入代理绕过地区限制
        proxy = self.settings.PROXY_URL
        if proxy:
            import py_clob_client.http_helpers.helpers as helpers
            helpers._http_client = httpx.Client(http2=True, proxy=proxy)

        pk = self.settings.POLYMARKET_PRIVATE_KEY
        if not pk.startswith("0x"):
            pk = "0x" + pk

        client = ClobClient(
            host="https://clob.polymarket.com",
            key=pk,
            chain_id=137,
            signature_type=0,
            funder=self.settings.POLYMARKET_FUNDER,
        )
        client.set_api_creds(ApiCreds(
            api_key=self.settings.POLYMARKET_API_KEY,
            api_secret=self.settings.POLYMARKET_API_SECRET,
            api_passphrase=self.settings.POLYMARKET_API_PASSPHRASE,
        ))
        self._clob_client = client
        return client

    def _submit_order(self, token_id: str, side: str, price: float, size: float) -> str:
        client = self._get_clob_client()
        order_side = BUY if side.upper() == "BUY" else SELL

        order_args = OrderArgs(
            price=price,
            size=size,
            side=order_side,
            token_id=token_id,
        )
        signed_order = client.create_order(order_args)
        resp = client.post_order(signed_order, OrderType.FOK)

        order_id = "unknown"
        if isinstance(resp, dict):
            order_id = resp.get("orderID", resp.get("order_id", "unknown"))

        logger.info(f"Order submitted: {side} {size}@{price} token={token_id[:12]}... → {order_id}")
        return order_id
