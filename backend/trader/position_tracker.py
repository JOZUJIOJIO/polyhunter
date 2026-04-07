from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import Market, Position, PnlSnapshot, Trade


class PositionTracker:
    def __init__(self, session: Session, total_balance: float = 0.0):
        self.session = session
        self.total_balance = total_balance

    def update_from_trade(self, trade: Trade) -> Position:
        existing = self.session.query(Position).filter(Position.market_id == trade.market_id, Position.token_id == trade.token_id).first()

        if existing and trade.side == "BUY":
            total_cost = (existing.avg_entry_price * existing.size) + (trade.price * trade.size)
            new_size = existing.size + trade.size
            existing.avg_entry_price = total_cost / new_size
            existing.size = new_size
            self.session.commit()
            return existing
        elif existing and trade.side == "SELL":
            existing.size -= trade.size
            if existing.size <= 0:
                self.session.delete(existing)
            self.session.commit()
            return existing
        else:
            market = self.session.get(Market, trade.market_id)
            side = "YES" if market and trade.token_id == market.token_id_yes else "NO"
            pos = Position(market_id=trade.market_id, token_id=trade.token_id, side=side, avg_entry_price=trade.price, size=trade.size, current_price=trade.price, unrealized_pnl=0.0)
            self.session.add(pos)
            self.session.commit()
            return pos

    def refresh_pnl(self) -> None:
        positions = self.session.query(Position).all()
        for pos in positions:
            market = self.session.get(Market, pos.market_id)
            if not market:
                continue
            if pos.side == "YES":
                pos.current_price = market.last_price_yes or pos.current_price
            else:
                pos.current_price = market.last_price_no or pos.current_price
            pos.unrealized_pnl = (pos.current_price - pos.avg_entry_price) * pos.size
        self.session.commit()

    def take_snapshot(self) -> PnlSnapshot:
        positions = self.session.query(Position).all()
        unrealized = sum(p.unrealized_pnl for p in positions)
        position_value = sum(p.current_price * p.size for p in positions)
        realized = self.session.query(func.sum(Trade.pnl)).filter(Trade.pnl.isnot(None)).scalar() or 0.0
        num_trades = self.session.query(func.count(Trade.id)).filter(Trade.status == "FILLED").scalar() or 0
        winning = self.session.query(func.count(Trade.id)).filter(Trade.pnl > 0).scalar() or 0
        win_rate = winning / num_trades if num_trades > 0 else 0.0
        total_value = self.total_balance + position_value + realized
        snapshot = PnlSnapshot(date=date.today(), total_value=total_value, realized_pnl=realized, unrealized_pnl=unrealized, num_trades=num_trades, win_rate=round(win_rate, 4))
        self.session.add(snapshot)
        self.session.commit()
        return snapshot
