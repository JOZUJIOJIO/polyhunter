from datetime import datetime, date
from pydantic import BaseModel


class MarketResponse(BaseModel):
    id: str
    condition_id: str
    question: str
    slug: str | None = None
    category: str | None = None
    end_date: datetime | None = None
    active: bool
    last_price_yes: float | None = None
    last_price_no: float | None = None
    volume_24h: float | None = None
    liquidity: float | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class SignalResponse(BaseModel):
    id: int
    market_id: str
    type: str
    source_detail: str | None = None
    current_price: float
    fair_value: float | None = None
    edge_pct: float
    confidence: int
    status: str
    created_at: datetime | None = None
    market_question: str | None = None
    model_config = {"from_attributes": True}


class TradeRequest(BaseModel):
    signal_id: int | None = None
    market_id: str
    token_id: str
    side: str
    price: float
    size: float


class TradeResponse(BaseModel):
    id: int
    signal_id: int | None = None
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    cost: float
    status: str
    order_id: str | None = None
    pnl: float | None = None
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    id: int
    market_id: str
    token_id: str
    side: str
    avg_entry_price: float
    size: float
    current_price: float
    unrealized_pnl: float
    market_question: str | None = None
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class OverviewResponse(BaseModel):
    total_balance: float
    unrealized_pnl: float
    realized_pnl: float
    active_positions: int
    active_signals: int
    today_trades: int
    win_rate: float


class RiskSettingsResponse(BaseModel):
    max_single_bet_pct: int
    max_daily_loss_pct: int
    max_position_pct: int
    min_edge_pct: float
    max_positions: int
    expiry_buffer_hours: int
    fee_pct: float
