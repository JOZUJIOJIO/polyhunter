# PolyHunter Plan B: Trading + API Implementation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the trading execution layer (risk manager, order executor, position tracker) and FastAPI REST API that powers the Web Dashboard.

**Architecture:** FastAPI serves REST endpoints for the frontend. Trading modules wrap py-clob-client for order execution with risk checks. All modules use the existing SQLAlchemy models from Plan A.

**Tech Stack:** FastAPI, uvicorn, py-clob-client, existing SQLAlchemy models, pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `backend/trader/__init__.py` | Package marker |
| `backend/trader/risk_manager.py` | Pre-trade risk checks (position limits, daily loss, etc.) |
| `backend/trader/executor.py` | Order execution via py-clob-client |
| `backend/trader/position_tracker.py` | Position + PnL tracking |
| `backend/api/__init__.py` | Package marker |
| `backend/api/schemas.py` | Pydantic request/response models |
| `backend/api/routes/__init__.py` | Package marker |
| `backend/api/routes/markets.py` | GET /api/markets |
| `backend/api/routes/signals.py` | GET /api/signals, POST /api/signals/{id}/dismiss |
| `backend/api/routes/trades.py` | POST /api/trades, GET /api/trades |
| `backend/api/routes/positions.py` | GET /api/positions |
| `backend/api/routes/overview.py` | GET /api/overview (dashboard summary) |
| `backend/main.py` | FastAPI app factory + scheduler startup |
| `tests/test_risk_manager.py` | Risk manager tests |
| `tests/test_executor.py` | Order executor tests (mocked) |
| `tests/test_position_tracker.py` | Position tracker tests |
| `tests/test_api_markets.py` | Markets API tests |
| `tests/test_api_signals.py` | Signals API tests |
| `tests/test_api_trades.py` | Trades API tests |
| `tests/test_api_overview.py` | Overview API tests |

---

### Task 1: Risk Manager

**Files:**
- Create: `backend/trader/__init__.py`
- Create: `backend/trader/risk_manager.py`
- Create: `tests/test_risk_manager.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_risk_manager.py`:

```python
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings
from backend.db.models import Base, Market, Trade, Position
from backend.trader.risk_manager import RiskManager, RiskCheckResult


@pytest.fixture
def risk_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True, last_price_yes=0.50, last_price_no=0.50,
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )
    session.add(market)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_passes_when_within_limits(risk_db):
    settings = Settings(
        RISK_MAX_SINGLE_BET_PCT=10,
        RISK_MAX_DAILY_LOSS_PCT=5,
        RISK_MAX_POSITION_PCT=20,
        RISK_MAX_POSITIONS=10,
    )
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=50.0, price=0.50)
    assert result.approved is True
    assert result.reason == ""


def test_rejects_exceeding_single_bet(risk_db):
    settings = Settings(RISK_MAX_SINGLE_BET_PCT=10)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    # cost = 150 * 0.50 = 75, which is 7.5% — within limit
    result = rm.check_order(market_id="m1", side="BUY", size=150.0, price=0.50)
    assert result.approved is True

    # cost = 250 * 0.50 = 125, which is 12.5% — exceeds 10%
    result = rm.check_order(market_id="m1", side="BUY", size=250.0, price=0.50)
    assert result.approved is False
    assert "single bet" in result.reason.lower()


def test_rejects_exceeding_position_concentration(risk_db):
    # Add existing position
    pos = Position(
        market_id="m1", token_id="ty1", side="YES",
        avg_entry_price=0.50, size=300.0, current_price=0.50, unrealized_pnl=0.0,
    )
    risk_db.add(pos)
    risk_db.commit()

    settings = Settings(RISK_MAX_POSITION_PCT=20)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    # Existing: 300 * 0.50 = 150. New: 100 * 0.50 = 50. Total: 200 = 20% — at limit
    result = rm.check_order(market_id="m1", side="BUY", size=100.0, price=0.50)
    assert result.approved is True

    # New: 150 * 0.50 = 75. Total: 225 = 22.5% — exceeds 20%
    result = rm.check_order(market_id="m1", side="BUY", size=150.0, price=0.50)
    assert result.approved is False
    assert "concentration" in result.reason.lower()


def test_rejects_exceeding_max_positions(risk_db):
    for i in range(10):
        m = Market(
            id=f"mx{i}", condition_id=f"cx{i}", token_id_yes=f"tyx{i}", token_id_no=f"tnx{i}",
            question=f"Q{i}?", active=True,
        )
        risk_db.add(m)
        pos = Position(
            market_id=f"mx{i}", token_id=f"tyx{i}", side="YES",
            avg_entry_price=0.50, size=10.0, current_price=0.50, unrealized_pnl=0.0,
        )
        risk_db.add(pos)
    risk_db.commit()

    settings = Settings(RISK_MAX_POSITIONS=10)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=10000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=10.0, price=0.50)
    assert result.approved is False
    assert "max positions" in result.reason.lower()


def test_rejects_near_expiry(risk_db):
    market = risk_db.get(Market, "m1")
    market.end_date = datetime.now(timezone.utc) + timedelta(hours=12)
    risk_db.commit()

    settings = Settings(RISK_EXPIRY_BUFFER_HOURS=24)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    result = rm.check_order(market_id="m1", side="BUY", size=10.0, price=0.50)
    assert result.approved is False
    assert "expir" in result.reason.lower()


def test_rejects_exceeding_daily_loss(risk_db):
    # Add losing trades from today
    for i in range(3):
        trade = Trade(
            market_id="m1", token_id="ty1", side="BUY",
            price=0.50, size=100.0, cost=50.0, status="FILLED",
            pnl=-20.0,  # lost $20 each
        )
        risk_db.add(trade)
    risk_db.commit()

    settings = Settings(RISK_MAX_DAILY_LOSS_PCT=5)
    rm = RiskManager(session=risk_db, settings=settings, total_balance=1000.0)
    # Daily loss = -60, which is 6% > 5%
    result = rm.check_order(market_id="m1", side="BUY", size=10.0, price=0.50)
    assert result.approved is False
    assert "daily loss" in result.reason.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_risk_manager.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement RiskManager**

Create `backend/trader/__init__.py` (empty).

Create `backend/trader/risk_manager.py`:

```python
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.db.models import Market, Position, Trade


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str = ""


class RiskManager:
    def __init__(self, session: Session, settings: Settings | None = None, total_balance: float = 0.0):
        self.session = session
        self.settings = settings or Settings()
        self.total_balance = total_balance

    def check_order(self, market_id: str, side: str, size: float, price: float) -> RiskCheckResult:
        cost = size * price

        # 1. Single bet limit
        max_bet = self.total_balance * (self.settings.RISK_MAX_SINGLE_BET_PCT / 100)
        if cost > max_bet:
            return RiskCheckResult(
                approved=False,
                reason=f"Single bet ${cost:.2f} exceeds limit ${max_bet:.2f} ({self.settings.RISK_MAX_SINGLE_BET_PCT}%)",
            )

        # 2. Position concentration
        existing_exposure = self._get_market_exposure(market_id)
        total_exposure = existing_exposure + cost
        max_exposure = self.total_balance * (self.settings.RISK_MAX_POSITION_PCT / 100)
        if total_exposure > max_exposure:
            return RiskCheckResult(
                approved=False,
                reason=f"Position concentration ${total_exposure:.2f} exceeds limit ${max_exposure:.2f} ({self.settings.RISK_MAX_POSITION_PCT}%)",
            )

        # 3. Max positions count
        distinct_markets = self._count_distinct_positions()
        has_existing = self._has_position_in_market(market_id)
        if not has_existing and distinct_markets >= self.settings.RISK_MAX_POSITIONS:
            return RiskCheckResult(
                approved=False,
                reason=f"Max positions ({self.settings.RISK_MAX_POSITIONS}) reached, cannot open new market",
            )

        # 4. Expiry buffer
        market = self.session.get(Market, market_id)
        if market and market.end_date:
            buffer = timedelta(hours=self.settings.RISK_EXPIRY_BUFFER_HOURS)
            if market.end_date - datetime.now(timezone.utc) < buffer:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Market expires within {self.settings.RISK_EXPIRY_BUFFER_HOURS}h buffer",
                )

        # 5. Daily loss limit
        daily_loss = self._get_daily_realized_loss()
        max_loss = self.total_balance * (self.settings.RISK_MAX_DAILY_LOSS_PCT / 100)
        if abs(daily_loss) > max_loss:
            return RiskCheckResult(
                approved=False,
                reason=f"Daily loss ${abs(daily_loss):.2f} exceeds limit ${max_loss:.2f} ({self.settings.RISK_MAX_DAILY_LOSS_PCT}%)",
            )

        return RiskCheckResult(approved=True)

    def _get_market_exposure(self, market_id: str) -> float:
        positions = (
            self.session.query(Position)
            .filter(Position.market_id == market_id)
            .all()
        )
        return sum(p.size * p.avg_entry_price for p in positions)

    def _count_distinct_positions(self) -> int:
        result = (
            self.session.query(func.count(func.distinct(Position.market_id)))
            .scalar()
        )
        return result or 0

    def _has_position_in_market(self, market_id: str) -> bool:
        return (
            self.session.query(Position)
            .filter(Position.market_id == market_id)
            .first()
        ) is not None

    def _get_daily_realized_loss(self) -> float:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = (
            self.session.query(func.sum(Trade.pnl))
            .filter(Trade.created_at >= today_start, Trade.pnl < 0)
            .scalar()
        )
        return result or 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_risk_manager.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/trader/ tests/test_risk_manager.py
git commit -m "feat: add RiskManager with 5 pre-trade risk checks"
```

---

### Task 2: Order Executor

**Files:**
- Create: `backend/trader/executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_executor.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings
from backend.db.models import Base, Market, Signal, Trade
from backend.trader.executor import OrderExecutor
from backend.trader.risk_manager import RiskCheckResult


@pytest.fixture
def exec_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True, last_price_yes=0.50, last_price_no=0.50,
    )
    session.add(market)
    signal = Signal(
        id=1, market_id="m1", type="ARBITRAGE", current_price=0.50,
        edge_pct=3.0, confidence=90, status="NEW",
    )
    session.add(signal)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_execute_order_success(exec_db):
    mock_risk = MagicMock()
    mock_risk.check_order.return_value = RiskCheckResult(approved=True)

    executor = OrderExecutor(session=exec_db, risk_manager=mock_risk)
    with patch.object(executor, "_submit_order", return_value="order_abc"):
        trade = executor.execute(
            signal_id=1, market_id="m1", token_id="ty1",
            side="BUY", price=0.50, size=100.0,
        )

    assert trade.status == "FILLED"
    assert trade.order_id == "order_abc"
    assert trade.cost == 50.0

    saved = exec_db.query(Trade).first()
    assert saved.order_id == "order_abc"

    signal = exec_db.query(Signal).get(1)
    assert signal.status == "ACTED"


def test_execute_order_rejected_by_risk(exec_db):
    mock_risk = MagicMock()
    mock_risk.check_order.return_value = RiskCheckResult(approved=False, reason="Too risky")

    executor = OrderExecutor(session=exec_db, risk_manager=mock_risk)
    trade = executor.execute(
        signal_id=1, market_id="m1", token_id="ty1",
        side="BUY", price=0.50, size=100.0,
    )

    assert trade is None
    assert exec_db.query(Trade).count() == 0


def test_execute_order_submission_fails(exec_db):
    mock_risk = MagicMock()
    mock_risk.check_order.return_value = RiskCheckResult(approved=True)

    executor = OrderExecutor(session=exec_db, risk_manager=mock_risk)
    with patch.object(executor, "_submit_order", side_effect=Exception("API error")):
        trade = executor.execute(
            signal_id=1, market_id="m1", token_id="ty1",
            side="BUY", price=0.50, size=100.0,
        )

    assert trade.status == "CANCELLED"
    saved = exec_db.query(Trade).first()
    assert saved.status == "CANCELLED"
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement OrderExecutor**

Create `backend/trader/executor.py`:

```python
import logging

from sqlalchemy.orm import Session

from backend.db.models import Signal, Trade
from backend.trader.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(self, session: Session, risk_manager: RiskManager):
        self.session = session
        self.risk_manager = risk_manager

    def execute(
        self,
        signal_id: int | None,
        market_id: str,
        token_id: str,
        side: str,
        price: float,
        size: float,
    ) -> Trade | None:
        cost = size * price

        # Risk check
        check = self.risk_manager.check_order(
            market_id=market_id, side=side, size=size, price=price,
        )
        if not check.approved:
            logger.warning(f"Order rejected by risk manager: {check.reason}")
            return None

        # Create trade record
        trade = Trade(
            signal_id=signal_id,
            market_id=market_id,
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            cost=cost,
            status="PENDING",
        )
        self.session.add(trade)
        self.session.commit()

        # Submit order
        try:
            order_id = self._submit_order(token_id, side, price, size)
            trade.status = "FILLED"
            trade.order_id = order_id
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            trade.status = "CANCELLED"

        # Update signal status
        if signal_id:
            signal = self.session.get(Signal, signal_id)
            if signal:
                signal.status = "ACTED"

        self.session.commit()
        return trade

    def _submit_order(self, token_id: str, side: str, price: float, size: float) -> str:
        """Submit order via py-clob-client. Override in tests."""
        # TODO: Integrate with py-clob-client in production
        # For now, this is a placeholder that will be mocked in tests
        raise NotImplementedError("Connect py-clob-client for live trading")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_executor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/trader/executor.py tests/test_executor.py
git commit -m "feat: add OrderExecutor with risk-checked order submission"
```

---

### Task 3: Position Tracker

**Files:**
- Create: `backend/trader/position_tracker.py`
- Create: `tests/test_position_tracker.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_position_tracker.py`:

```python
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Market, Trade, Position, PnlSnapshot
from backend.trader.position_tracker import PositionTracker


@pytest.fixture
def tracker_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True, last_price_yes=0.60, last_price_no=0.40,
    )
    session.add(market)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_update_position_from_buy_trade(tracker_db):
    trade = Trade(
        market_id="m1", token_id="ty1", side="BUY",
        price=0.50, size=100.0, cost=50.0, status="FILLED",
    )
    tracker_db.add(trade)
    tracker_db.commit()

    tracker = PositionTracker(session=tracker_db)
    tracker.update_from_trade(trade)

    pos = tracker_db.query(Position).first()
    assert pos is not None
    assert pos.market_id == "m1"
    assert pos.token_id == "ty1"
    assert pos.side == "YES"
    assert pos.avg_entry_price == 0.50
    assert pos.size == 100.0


def test_update_position_averages_price(tracker_db):
    # Existing position
    pos = Position(
        market_id="m1", token_id="ty1", side="YES",
        avg_entry_price=0.40, size=100.0, current_price=0.50, unrealized_pnl=10.0,
    )
    tracker_db.add(pos)
    tracker_db.commit()

    trade = Trade(
        market_id="m1", token_id="ty1", side="BUY",
        price=0.60, size=100.0, cost=60.0, status="FILLED",
    )
    tracker_db.add(trade)
    tracker_db.commit()

    tracker = PositionTracker(session=tracker_db)
    tracker.update_from_trade(trade)

    pos = tracker_db.query(Position).first()
    assert pos.size == 200.0
    assert pos.avg_entry_price == pytest.approx(0.50)  # (100*0.40 + 100*0.60) / 200


def test_refresh_unrealized_pnl(tracker_db):
    pos = Position(
        market_id="m1", token_id="ty1", side="YES",
        avg_entry_price=0.40, size=100.0, current_price=0.50, unrealized_pnl=0.0,
    )
    tracker_db.add(pos)
    tracker_db.commit()

    tracker = PositionTracker(session=tracker_db)
    tracker.refresh_pnl()

    pos = tracker_db.query(Position).first()
    assert pos.current_price == 0.60  # from market.last_price_yes
    assert pos.unrealized_pnl == pytest.approx(20.0)  # (0.60 - 0.40) * 100


def test_take_pnl_snapshot(tracker_db):
    pos = Position(
        market_id="m1", token_id="ty1", side="YES",
        avg_entry_price=0.40, size=100.0, current_price=0.60, unrealized_pnl=20.0,
    )
    tracker_db.add(pos)

    trade = Trade(
        market_id="m1", token_id="ty1", side="BUY",
        price=0.40, size=100.0, cost=40.0, status="FILLED", pnl=15.0,
    )
    tracker_db.add(trade)
    tracker_db.commit()

    tracker = PositionTracker(session=tracker_db, total_balance=1000.0)
    snapshot = tracker.take_snapshot()

    assert snapshot.total_value > 0
    assert snapshot.unrealized_pnl == 20.0
    assert snapshot.realized_pnl == 15.0
    assert snapshot.num_trades == 1
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement PositionTracker**

Create `backend/trader/position_tracker.py`:

```python
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import Market, Position, PnlSnapshot, Trade


class PositionTracker:
    def __init__(self, session: Session, total_balance: float = 0.0):
        self.session = session
        self.total_balance = total_balance

    def update_from_trade(self, trade: Trade) -> Position:
        existing = (
            self.session.query(Position)
            .filter(Position.market_id == trade.market_id, Position.token_id == trade.token_id)
            .first()
        )

        if existing and trade.side == "BUY":
            # Average up
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
            # Determine side from token_id
            market = self.session.get(Market, trade.market_id)
            side = "YES" if market and trade.token_id == market.token_id_yes else "NO"

            pos = Position(
                market_id=trade.market_id,
                token_id=trade.token_id,
                side=side,
                avg_entry_price=trade.price,
                size=trade.size,
                current_price=trade.price,
                unrealized_pnl=0.0,
            )
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

        snapshot = PnlSnapshot(
            date=date.today(),
            total_value=total_value,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            num_trades=num_trades,
            win_rate=round(win_rate, 4),
        )
        self.session.add(snapshot)
        self.session.commit()
        return snapshot
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_position_tracker.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/trader/position_tracker.py tests/test_position_tracker.py
git commit -m "feat: add PositionTracker for position + PnL management"
```

---

### Task 4: FastAPI App + Schemas

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/schemas.py`
- Create: `backend/api/routes/__init__.py`
- Create: `backend/main.py`

- [ ] **Step 1: Update pyproject.toml dependencies**

Add `fastapi` and `uvicorn` to dependencies in `pyproject.toml`:

```toml
dependencies = [
    "sqlalchemy>=2.0",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "apscheduler>=3.10",
    "py-clob-client>=0.34",
    "fastapi>=0.115",
    "uvicorn>=0.34",
]
```

Then: `pip install -e ".[dev]"`

- [ ] **Step 2: Create schemas**

Create `backend/api/__init__.py` (empty).
Create `backend/api/routes/__init__.py` (empty).

Create `backend/api/schemas.py`:

```python
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
    side: str  # BUY or SELL
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
```

- [ ] **Step 3: Create FastAPI main app**

Create `backend/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import Settings
from backend.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = Settings()
    init_db(settings)
    yield
    # Shutdown (nothing needed for now)


def create_app() -> FastAPI:
    app = FastAPI(title="PolyHunter API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.api.routes.markets import router as markets_router
    from backend.api.routes.signals import router as signals_router
    from backend.api.routes.trades import router as trades_router
    from backend.api.routes.positions import router as positions_router
    from backend.api.routes.overview import router as overview_router

    app.include_router(markets_router, prefix="/api")
    app.include_router(signals_router, prefix="/api")
    app.include_router(trades_router, prefix="/api")
    app.include_router(positions_router, prefix="/api")
    app.include_router(overview_router, prefix="/api")

    return app


app = create_app()
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/ backend/main.py pyproject.toml
git commit -m "feat: add FastAPI app with schemas and CORS setup"
```

---

### Task 5: API Routes

**Files:**
- Create: `backend/api/routes/markets.py`
- Create: `backend/api/routes/signals.py`
- Create: `backend/api/routes/trades.py`
- Create: `backend/api/routes/positions.py`
- Create: `backend/api/routes/overview.py`
- Create: `tests/test_api_markets.py`
- Create: `tests/test_api_signals.py`
- Create: `tests/test_api_trades.py`
- Create: `tests/test_api_overview.py`

- [ ] **Step 1: Create shared test fixture**

Add to `tests/conftest.py`:

```python
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.db.database import get_engine, get_session_factory

@pytest.fixture
def test_app(db_session):
    """FastAPI test client with in-memory DB."""
    app = create_app()

    def override_get_db():
        yield db_session

    from backend.api.deps import get_db
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client, db_session
```

Create `backend/api/deps.py`:

```python
from sqlalchemy.orm import Session
from backend.db.database import get_session_factory


def get_db():
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 2: Implement markets route + test**

Create `backend/api/routes/markets.py`:

```python
from fastapi import APIRouter, Depends, Query
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
    sort_by: str = Query(default="volume_24h", regex="^(volume_24h|liquidity|updated_at)$"),
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

    sort_col = getattr(Market, sort_by)
    query = query.order_by(sort_col.desc().nullslast())
    return query.offset(offset).limit(limit).all()


@router.get("/markets/{market_id}", response_model=MarketResponse)
def get_market(market_id: str, db: Session = Depends(get_db)):
    market = db.get(Market, market_id)
    if not market:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Market not found")
    return market
```

Create `tests/test_api_markets.py`:

```python
from fastapi.testclient import TestClient
from backend.db.models import Market


def test_list_markets(test_app):
    client, db = test_app
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True, last_price_yes=0.50, last_price_no=0.50,
        volume_24h=10000, category="politics",
    )
    db.add(market)
    db.commit()

    resp = client.get("/api/markets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "m1"


def test_list_markets_filter_active(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Active?", active=True))
    db.add(Market(id="m2", condition_id="c2", token_id_yes="t3", token_id_no="t4", question="Closed?", active=False))
    db.commit()

    resp = client.get("/api/markets?active=true")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_market_not_found(test_app):
    client, _ = test_app
    resp = client.get("/api/markets/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 3: Implement signals route + test**

Create `backend/api/routes/signals.py`:

```python
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
```

Create `tests/test_api_signals.py`:

```python
from backend.db.models import Market, Signal


def test_list_signals(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    db.add(Signal(market_id="m1", type="ARBITRAGE", current_price=0.50, edge_pct=3.0, confidence=90, status="NEW"))
    db.commit()

    resp = client.get("/api/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "ARBITRAGE"
    assert data[0]["market_question"] == "Q?"


def test_dismiss_signal(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    db.add(Signal(market_id="m1", type="ARBITRAGE", current_price=0.50, edge_pct=3.0, confidence=90, status="NEW"))
    db.commit()

    signal = db.query(Signal).first()
    resp = client.post(f"/api/signals/{signal.id}/dismiss")
    assert resp.status_code == 200

    db.refresh(signal)
    assert signal.status == "DISMISSED"
```

- [ ] **Step 4: Implement trades route + test**

Create `backend/api/routes/trades.py`:

```python
from fastapi import APIRouter, Depends, Query, HTTPException
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
        signal_id=req.signal_id,
        market_id=req.market_id,
        token_id=req.token_id,
        side=req.side,
        price=req.price,
        size=req.size,
        cost=req.price * req.size,
        status="PENDING",
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade
```

Create `tests/test_api_trades.py`:

```python
from backend.db.models import Market, Trade


def test_list_trades(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    db.add(Trade(market_id="m1", token_id="t1", side="BUY", price=0.50, size=100, cost=50, status="FILLED"))
    db.commit()

    resp = client.get("/api/trades")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_trade(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()

    resp = client.post("/api/trades", json={
        "market_id": "m1", "token_id": "t1", "side": "BUY", "price": 0.50, "size": 100,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["cost"] == 50.0
```

- [ ] **Step 5: Implement positions and overview routes + test**

Create `backend/api/routes/positions.py`:

```python
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
```

Create `backend/api/routes/overview.py`:

```python
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
        total_balance=0.0,  # Will be set from config/wallet in production
        unrealized_pnl=unrealized,
        realized_pnl=realized,
        active_positions=len(positions),
        active_signals=active_signals,
        today_trades=today_trades,
        win_rate=round(win_rate, 4),
    )
```

Create `tests/test_api_overview.py`:

```python
from backend.db.models import Market, Signal, Position


def test_overview_empty(test_app):
    client, _ = test_app
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_positions"] == 0
    assert data["active_signals"] == 0


def test_overview_with_data(test_app):
    client, db = test_app
    db.add(Market(id="m1", condition_id="c1", token_id_yes="t1", token_id_no="t2", question="Q?", active=True))
    db.commit()
    db.add(Position(market_id="m1", token_id="t1", side="YES", avg_entry_price=0.40, size=100, current_price=0.60, unrealized_pnl=20))
    db.add(Signal(market_id="m1", type="ARBITRAGE", current_price=0.50, edge_pct=3.0, confidence=90, status="NEW"))
    db.commit()

    resp = client.get("/api/overview")
    data = resp.json()
    assert data["active_positions"] == 1
    assert data["active_signals"] == 1
    assert data["unrealized_pnl"] == 20.0
```

- [ ] **Step 6: Run all API tests**

```bash
pytest tests/test_api_*.py -v
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add backend/api/ tests/test_api_*.py
git commit -m "feat: add FastAPI routes for markets, signals, trades, positions, overview"
```

---

### Task 6: Full Integration Test

- [ ] **Step 1: Run entire test suite**

```bash
pytest -v
```

Expected: All tests pass (26 from Plan A + ~19 from Plan B = ~45 tests).

- [ ] **Step 2: Verify server starts**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/量化交易"
source .venv/bin/activate
timeout 5 uvicorn backend.main:app --host 0.0.0.0 --port 8000 || true
```

Expected: Server starts without import errors.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: Plan B complete - trading layer + FastAPI API"
```
