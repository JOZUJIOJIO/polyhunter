from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import OverviewResponse
from backend.db.models import Position, Signal, Trade

router = APIRouter()


@router.get("/overview", response_model=OverviewResponse)
def get_overview(db: Session = Depends(get_db)):
    positions = db.query(Position).all()
    unrealized = sum(p.unrealized_pnl for p in positions)
    realized = db.query(func.sum(Trade.pnl)).filter(Trade.pnl.isnot(None)).scalar() or 0.0
    total_trades = db.query(func.count(Trade.id)).filter(Trade.status == "FILLED").scalar() or 0
    winning = db.query(func.count(Trade.id)).filter(Trade.pnl > 0).scalar() or 0
    win_rate = winning / total_trades if total_trades > 0 else 0.0
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_trades = db.query(func.count(Trade.id)).filter(Trade.created_at >= today).scalar() or 0
    active_signals = db.query(func.count(Signal.id)).filter(Signal.status == "NEW").scalar() or 0
    return OverviewResponse(
        total_balance=0.0, unrealized_pnl=unrealized, realized_pnl=realized,
        active_positions=len(positions), active_signals=active_signals,
        today_trades=today_trades, win_rate=round(win_rate, 4),
    )
