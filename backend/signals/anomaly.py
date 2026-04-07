import json
import statistics

from sqlalchemy.orm import Session

from backend.db.models import Market, Signal
from backend.signals.base import SignalDetector


class AnomalyDetector(SignalDetector):
    def __init__(
        self,
        session: Session,
        sigma_threshold: float = 2.0,
        min_volume: float = 1000.0,
        min_history: int = 10,
    ):
        super().__init__(session)
        self.sigma_threshold = sigma_threshold
        self.min_volume = min_volume
        self.min_history = min_history

    def detect(self, price_histories: dict[str, list[dict]]) -> list[Signal]:
        markets = (
            self.session.query(Market)
            .filter(Market.active == True, Market.last_price_yes.isnot(None))
            .all()
        )

        signals = []
        for market in markets:
            history = price_histories.get(market.id, [])
            signal = self._check_anomaly(market, history)
            if signal:
                signals.append(signal)
        return signals

    def _check_anomaly(self, market: Market, history: list[dict]) -> Signal | None:
        if len(history) < self.min_history:
            return None

        if (market.volume_24h or 0) < self.min_volume:
            return None

        prices = [h["p"] for h in history]
        mean = statistics.mean(prices)
        stdev = statistics.stdev(prices)

        if stdev == 0:
            return None

        current = market.last_price_yes
        z_score = (current - mean) / stdev

        if abs(z_score) < self.sigma_threshold:
            return None

        edge_pct = abs(current - mean) / mean * 100

        return Signal(
            market_id=market.id,
            type="PRICE_ANOMALY",
            source_detail=json.dumps({
                "current_price": current,
                "mean_price": round(mean, 4),
                "stdev": round(stdev, 4),
                "z_score": round(z_score, 2),
                "direction": "UP" if z_score > 0 else "DOWN",
                "volume_24h": market.volume_24h,
            }),
            current_price=current,
            fair_value=round(mean, 4),
            edge_pct=round(edge_pct, 2),
            confidence=min(int(abs(z_score) * 25), 100),
            status="NEW",
        )
