"""Bitget exchange API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.config import Settings
from backend.db.models import BitgetTrade, Alert
from backend.exchanges.bitget.adapter import BitgetAdapter
from backend.exchanges.base import OrderRequest, OrderSide, OrderType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bitget", tags=["bitget"])

_adapter: BitgetAdapter | None = None


def _get_adapter() -> BitgetAdapter:
    global _adapter
    if _adapter is None:
        _adapter = BitgetAdapter()
    return _adapter


class PlaceOrderRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str = "MARKET"  # "MARKET" or "LIMIT"
    size: float
    price: float | None = None


@router.get("/balance")
async def get_balance():
    adapter = _get_adapter()
    try:
        balance = await adapter.get_balance()
        return {"balance": balance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions():
    adapter = _get_adapter()
    try:
        positions = await adapter.get_positions()
        return {
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "size": p.size,
                    "avg_entry_price": p.avg_entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "leverage": p.leverage,
                }
                for p in positions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str):
    adapter = _get_adapter()
    try:
        ticker = await adapter.get_ticker(symbol)
        return {
            "symbol": ticker.symbol,
            "last_price": ticker.last_price,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "high_24h": ticker.high_24h,
            "low_24h": ticker.low_24h,
            "volume_24h": ticker.volume_24h,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order")
async def place_order(req: PlaceOrderRequest, db: Session = Depends(get_db)):
    adapter = _get_adapter()
    settings = Settings()

    # Size limit check
    cost = req.size * (req.price or 0)
    if cost > settings.BITGET_MAX_POSITION_USD:
        raise HTTPException(
            status_code=400,
            detail=f"Order cost ${cost:.2f} exceeds max position ${settings.BITGET_MAX_POSITION_USD}",
        )

    try:
        order_req = OrderRequest(
            symbol=req.symbol,
            side=OrderSide(req.side.upper()),
            order_type=OrderType(req.order_type.upper()),
            size=req.size,
            price=req.price,
        )
        result = await adapter.place_order(order_req)

        trade = BitgetTrade(
            symbol=req.symbol,
            side=req.side.upper(),
            order_type=req.order_type.upper(),
            price=result.price,
            size=result.size,
            cost=result.price * result.size,
            status=result.status.value,
            order_id=result.order_id,
        )
        db.add(trade)
        db.commit()

        return {
            "order_id": result.order_id,
            "status": result.status.value,
            "trade_id": trade.id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades")
async def list_trades(limit: int = 50, db: Session = Depends(get_db)):
    trades = (
        db.query(BitgetTrade)
        .order_by(BitgetTrade.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "order_type": t.order_type,
                "price": t.price,
                "size": t.size,
                "cost": t.cost,
                "status": t.status,
                "order_id": t.order_id,
                "strategy": t.strategy,
                "pnl": t.pnl,
                "created_at": t.created_at.isoformat(),
            }
            for t in trades
        ]
    }


@router.get("/alerts")
async def list_alerts(limit: int = 50, db: Session = Depends(get_db)):
    alerts = (
        db.query(Alert)
        .filter(Alert.exchange == "bitget")
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "alerts": [
            {
                "id": a.id,
                "symbol": a.symbol,
                "type": a.type,
                "message": a.message,
                "acknowledged": a.acknowledged,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ]
    }
