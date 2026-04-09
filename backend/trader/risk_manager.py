import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.db.models import Market, Position, Trade

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str = ""


class RiskManager:
    def __init__(self, session: Session, settings: Settings | None = None, total_balance: float = 0.0):
        self.session = session
        self.settings = settings or Settings()
        self.total_balance = total_balance
        self._circuit_tripped_at: datetime | None = None

    def check_order(self, market_id: str, side: str, size: float, price: float) -> RiskCheckResult:
        # 熔断检查（最先执行）
        cb_result = self._check_circuit_breaker()
        if not cb_result.approved:
            return cb_result

        cost = size * price

        max_bet = self.total_balance * (self.settings.RISK_MAX_SINGLE_BET_PCT / 100)
        if cost > max_bet:
            return RiskCheckResult(approved=False, reason=f"Single bet ${cost:.2f} exceeds limit ${max_bet:.2f} ({self.settings.RISK_MAX_SINGLE_BET_PCT}%)")

        existing_exposure = self._get_market_exposure(market_id)
        total_exposure = existing_exposure + cost
        max_exposure = self.total_balance * (self.settings.RISK_MAX_POSITION_PCT / 100)
        if total_exposure > max_exposure:
            return RiskCheckResult(approved=False, reason=f"Position concentration ${total_exposure:.2f} exceeds limit ${max_exposure:.2f} ({self.settings.RISK_MAX_POSITION_PCT}%)")

        distinct_markets = self._count_distinct_positions()
        has_existing = self._has_position_in_market(market_id)
        if not has_existing and distinct_markets >= self.settings.RISK_MAX_POSITIONS:
            return RiskCheckResult(approved=False, reason=f"Max positions ({self.settings.RISK_MAX_POSITIONS}) reached, cannot open new market")

        market = self.session.get(Market, market_id)
        if market and market.end_date:
            buffer = timedelta(hours=self.settings.RISK_EXPIRY_BUFFER_HOURS)
            end_date = market.end_date
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            if end_date - datetime.now(timezone.utc) < buffer:
                return RiskCheckResult(approved=False, reason=f"Market expires within {self.settings.RISK_EXPIRY_BUFFER_HOURS}h buffer")

        daily_loss = self._get_daily_realized_loss()
        max_loss = self.total_balance * (self.settings.RISK_MAX_DAILY_LOSS_PCT / 100)
        if abs(daily_loss) > max_loss:
            return RiskCheckResult(approved=False, reason=f"Daily loss ${abs(daily_loss):.2f} exceeds limit ${max_loss:.2f} ({self.settings.RISK_MAX_DAILY_LOSS_PCT}%)")

        return RiskCheckResult(approved=True)

    def _check_circuit_breaker(self) -> RiskCheckResult:
        """连续亏损熔断检查"""
        max_consecutive = self.settings.CIRCUIT_BREAKER_CONSECUTIVE_LOSSES
        cooldown_minutes = self.settings.CIRCUIT_BREAKER_COOLDOWN_MINUTES

        # 如果已经在冷却期内，检查是否已过冷却时间
        if self._circuit_tripped_at:
            elapsed = datetime.now(timezone.utc) - self._circuit_tripped_at
            if elapsed < timedelta(minutes=cooldown_minutes):
                remaining = cooldown_minutes - int(elapsed.total_seconds() / 60)
                return RiskCheckResult(
                    approved=False,
                    reason=f"Circuit breaker active: cooling down ({remaining}min remaining)",
                )
            else:
                # 冷却结束，重置
                logger.info("Circuit breaker cooldown expired, resuming trading")
                self._circuit_tripped_at = None

        # 查询最近 N 笔已成交的交易
        recent_trades = (
            self.session.query(Trade)
            .filter(Trade.status == "FILLED", Trade.pnl.isnot(None))
            .order_by(Trade.created_at.desc())
            .limit(max_consecutive)
            .all()
        )

        if len(recent_trades) >= max_consecutive:
            all_losses = all(t.pnl < 0 for t in recent_trades)
            if all_losses:
                self._circuit_tripped_at = datetime.now(timezone.utc)
                total_loss = sum(t.pnl for t in recent_trades)
                logger.warning(
                    f"Circuit breaker TRIPPED: {max_consecutive} consecutive losses "
                    f"(total ${total_loss:.2f}), pausing for {cooldown_minutes}min"
                )
                return RiskCheckResult(
                    approved=False,
                    reason=f"Circuit breaker: {max_consecutive} consecutive losses (${total_loss:.2f}), "
                    f"pausing for {cooldown_minutes}min",
                )

        return RiskCheckResult(approved=True)

    def is_circuit_breaker_active(self) -> bool:
        """供外部查询熔断状态"""
        result = self._check_circuit_breaker()
        return not result.approved

    def _get_market_exposure(self, market_id: str) -> float:
        positions = self.session.query(Position).filter(Position.market_id == market_id).all()
        return sum(p.size * p.avg_entry_price for p in positions)

    def _count_distinct_positions(self) -> int:
        result = self.session.query(func.count(func.distinct(Position.market_id))).scalar()
        return result or 0

    def _has_position_in_market(self, market_id: str) -> bool:
        return self.session.query(Position).filter(Position.market_id == market_id).first() is not None

    def _get_daily_realized_loss(self) -> float:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = self.session.query(func.sum(Trade.pnl)).filter(Trade.created_at >= today_start, Trade.pnl < 0).scalar()
        return result or 0.0
