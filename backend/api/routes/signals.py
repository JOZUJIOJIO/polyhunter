from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import SignalResponse
from backend.db.models import Signal, Market

router = APIRouter()


@router.get("/signals", response_model=list[SignalResponse])
def list_signals(
    status: str | None = None,
    signal_type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Signal)
    if status:
        query = query.filter(Signal.status == status)
    if signal_type:
        query = query.filter(Signal.type == signal_type)
    signals = query.order_by(Signal.created_at.desc()).offset(offset).limit(limit).all()
    results = []
    for s in signals:
        market = db.get(Market, s.market_id)
        resp = SignalResponse.model_validate(s)
        resp.market_question = market.question if market else None
        results.append(resp)
    return results


@router.post("/signals/{signal_id}/dismiss")
def dismiss_signal(signal_id: int, db: Session = Depends(get_db)):
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal.status = "DISMISSED"
    db.commit()
    return {"status": "ok"}
