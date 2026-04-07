from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import PositionResponse
from backend.db.models import Position, Market

router = APIRouter()


@router.get("/positions", response_model=list[PositionResponse])
def list_positions(db: Session = Depends(get_db)):
    positions = db.query(Position).all()
    results = []
    for p in positions:
        market = db.get(Market, p.market_id)
        resp = PositionResponse.model_validate(p)
        resp.market_question = market.question if market else None
        results.append(resp)
    return results
