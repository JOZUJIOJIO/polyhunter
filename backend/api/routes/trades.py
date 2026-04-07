from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import TradeRequest, TradeResponse
from backend.db.models import Trade

router = APIRouter()


@router.get("/trades", response_model=list[TradeResponse])
def list_trades(
    market_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Trade)
    if market_id:
        query = query.filter(Trade.market_id == market_id)
    if status:
        query = query.filter(Trade.status == status)
    return query.order_by(Trade.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/trades", response_model=TradeResponse)
def create_trade(req: TradeRequest, db: Session = Depends(get_db)):
    trade = Trade(
        signal_id=req.signal_id, market_id=req.market_id, token_id=req.token_id,
        side=req.side, price=req.price, size=req.size, cost=req.price * req.size, status="PENDING",
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade
