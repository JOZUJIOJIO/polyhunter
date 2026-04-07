import json

from sqlalchemy.orm import Session

from backend.config import Settings
from backend.db.models import Market, Signal
from backend.signals.base import SignalDetector


class ArbitrageDetector(SignalDetector):
    def __init__(self, session: Session, settings: Settings | None = None):
        super().__init__(session)
        self.settings = settings or Settings()

    def detect(self) -> list[Signal]:
        markets = (
            self.session.query(Market)
            .filter(
                Market.active == True,
                Market.last_price_yes.isnot(None),
                Market.last_price_no.isnot(None),
            )
            .all()
        )

        signals = []
        for market in markets:
            signal = self._check_yes_no_arb(market)
            if signal:
                signals.append(signal)
        return signals

    def _check_yes_no_arb(self, market: Market) -> Signal | None:
        yes_price = market.last_price_yes
        no_price = market.last_price_no
        total_cost = yes_price + no_price

        # If total < 1.0, buying both YES and NO guarantees profit of (1.0 - total)
        if total_cost >= 1.0:
            return None

        gap = 1.0 - total_cost
        gross_edge_pct = (gap / total_cost) * 100
        net_edge_pct = gross_edge_pct - self.settings.POLYMARKET_FEE_PCT

        if net_edge_pct < self.settings.RISK_MIN_EDGE_PCT:
            return None

        return Signal(
            market_id=market.id,
            type="ARBITRAGE",
            source_detail=json.dumps({
                "yes_price": yes_price,
                "no_price": no_price,
                "total_cost": round(total_cost, 4),
                "gross_edge_pct": round(gross_edge_pct, 2),
                "net_edge_pct": round(net_edge_pct, 2),
                "strategy": "buy_both",
            }),
            current_price=yes_price,
            fair_value=1.0 - no_price,
            edge_pct=round(net_edge_pct, 2),
            confidence=95,
            status="NEW",
        )
