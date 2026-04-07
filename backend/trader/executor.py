import logging

from sqlalchemy.orm import Session

from backend.db.models import Signal, Trade
from backend.trader.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(self, session: Session, risk_manager: RiskManager):
        self.session = session
        self.risk_manager = risk_manager

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

    def _submit_order(self, token_id: str, side: str, price: float, size: float) -> str:
        raise NotImplementedError("Connect py-clob-client for live trading")
