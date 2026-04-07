from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import MarketResponse
from backend.db.models import Market

router = APIRouter()


@router.get("/markets", response_model=list[MarketResponse])
def list_markets(
    active: bool | None = None,
    category: str | None = None,
    search: str | None = None,
    sort_by: str = Query(default="volume_24h"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Market)
    if active is not None:
        query = query.filter(Market.active == active)
    if category:
        query = query.filter(Market.category == category)
    if search:
        query = query.filter(Market.question.ilike(f"%{search}%"))
    sort_col = getattr(Market, sort_by, Market.volume_24h)
    query = query.order_by(sort_col.desc().nullslast())
    return query.offset(offset).limit(limit).all()


@router.get("/markets/{market_id}", response_model=MarketResponse)
def get_market(market_id: str, db: Session = Depends(get_db)):
    market = db.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return market
