# PolyHunter Plan A: Backend Core Implementation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend data layer, market/price crawlers, and signal engine (arbitrage + anomaly detection) for the PolyHunter Polymarket trading system.

**Architecture:** Python monorepo with SQLAlchemy ORM on SQLite, httpx for async HTTP, APScheduler for periodic tasks. All modules are independently testable with no external API dependency in tests (mocked HTTP).

**Tech Stack:** Python 3.11+, SQLAlchemy 2.x, httpx, APScheduler, pytest, pytest-asyncio

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Project metadata + dependencies |
| `backend/__init__.py` | Package marker |
| `backend/config.py` | Pydantic Settings — env vars, risk params |
| `backend/db/__init__.py` | Package marker |
| `backend/db/database.py` | Engine + session factory + create_all |
| `backend/db/models.py` | SQLAlchemy ORM: Market, Signal, Trade, Position, PnlSnapshot |
| `backend/crawler/__init__.py` | Package marker |
| `backend/crawler/gamma_client.py` | Gamma API HTTP client (market discovery) |
| `backend/crawler/clob_client.py` | CLOB API HTTP client (prices/orderbook) |
| `backend/crawler/market_crawler.py` | MarketCrawler: sync markets from Gamma → DB |
| `backend/crawler/price_crawler.py` | PriceCrawler: fetch prices from CLOB → DB |
| `backend/signals/__init__.py` | Package marker |
| `backend/signals/base.py` | SignalDetector base class |
| `backend/signals/arbitrage.py` | ArbitrageDetector: YES+NO mispricing |
| `backend/signals/anomaly.py` | AnomalyDetector: price deviation from mean |
| `tests/conftest.py` | Shared fixtures (in-memory DB, test session) |
| `tests/test_config.py` | Config loading tests |
| `tests/test_models.py` | ORM model CRUD tests |
| `tests/test_gamma_client.py` | Gamma API client tests (mocked HTTP) |
| `tests/test_clob_client.py` | CLOB API client tests (mocked HTTP) |
| `tests/test_market_crawler.py` | MarketCrawler integration tests |
| `tests/test_price_crawler.py` | PriceCrawler integration tests |
| `tests/test_arbitrage.py` | Arbitrage signal detection tests |
| `tests/test_anomaly.py` | Anomaly signal detection tests |
| `.env.example` | Environment variable template |
| `.gitignore` | Python + Node ignores |

---

### Task 1: Project Skeleton + Git Init

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `backend/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/量化交易"
git init
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/
*.db

# Environment
.env

# IDE
.vscode/
.idea/

# Node (for frontend later)
node_modules/
.next/

# OS
.DS_Store
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "polyhunter"
version = "0.1.0"
description = "Polymarket quantitative trading system"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy>=2.0",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "apscheduler>=3.10",
    "py-clob-client>=0.34",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-httpx>=0.34",
    "ruff>=0.8",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
```

- [ ] **Step 4: Create `.env.example`**

```env
# Polymarket
POLYMARKET_PRIVATE_KEY=
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=

# Database
DATABASE_URL=sqlite:///./polyhunter.db

# Risk Management
RISK_MAX_SINGLE_BET_PCT=10
RISK_MAX_DAILY_LOSS_PCT=5
RISK_MAX_POSITION_PCT=20
RISK_MIN_EDGE_PCT=1
RISK_MAX_POSITIONS=10
RISK_EXPIRY_BUFFER_HOURS=24

# Telegram (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Phase 2: AI
ANTHROPIC_API_KEY=
```

- [ ] **Step 5: Create `backend/__init__.py`**

```python
```

(Empty file — package marker only.)

- [ ] **Step 6: Install dependencies**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/量化交易"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

- [ ] **Step 7: Verify setup**

```bash
python -c "import sqlalchemy; import httpx; import pydantic; print('OK')"
pytest --co -q
```

Expected: prints `OK`, pytest discovers 0 tests (no test files yet).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore .env.example backend/__init__.py
git commit -m "chore: initialize project skeleton with dependencies"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `backend/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for config**

Create `tests/test_config.py`:

```python
import os
from backend.config import Settings


def test_settings_defaults():
    settings = Settings(
        POLYMARKET_PRIVATE_KEY="0xtest",
        POLYMARKET_API_KEY="test_key",
        POLYMARKET_API_SECRET="test_secret",
    )
    assert settings.DATABASE_URL == "sqlite:///./polyhunter.db"
    assert settings.RISK_MAX_SINGLE_BET_PCT == 10
    assert settings.RISK_MAX_DAILY_LOSS_PCT == 5
    assert settings.RISK_MAX_POSITION_PCT == 20
    assert settings.RISK_MIN_EDGE_PCT == 1.0
    assert settings.RISK_MAX_POSITIONS == 10
    assert settings.RISK_EXPIRY_BUFFER_HOURS == 24
    assert settings.POLYMARKET_FEE_PCT == 2.0


def test_settings_custom_values():
    settings = Settings(
        POLYMARKET_PRIVATE_KEY="0xtest",
        POLYMARKET_API_KEY="key",
        POLYMARKET_API_SECRET="secret",
        RISK_MAX_SINGLE_BET_PCT=5,
        RISK_MIN_EDGE_PCT=2.5,
    )
    assert settings.RISK_MAX_SINGLE_BET_PCT == 5
    assert settings.RISK_MIN_EDGE_PCT == 2.5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.config'`

- [ ] **Step 3: Implement config**

Create `backend/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Polymarket credentials
    POLYMARKET_PRIVATE_KEY: str = ""
    POLYMARKET_API_KEY: str = ""
    POLYMARKET_API_SECRET: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./polyhunter.db"

    # Risk management
    RISK_MAX_SINGLE_BET_PCT: int = 10
    RISK_MAX_DAILY_LOSS_PCT: int = 5
    RISK_MAX_POSITION_PCT: int = 20
    RISK_MIN_EDGE_PCT: float = 1.0
    RISK_MAX_POSITIONS: int = 10
    RISK_EXPIRY_BUFFER_HOURS: int = 24

    # Polymarket fee (used in edge calculations)
    POLYMARKET_FEE_PCT: float = 2.0

    # Telegram (optional)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Phase 2: AI
    ANTHROPIC_API_KEY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/config.py tests/test_config.py
git commit -m "feat: add configuration module with Pydantic Settings"
```

---

### Task 3: Database + ORM Models

**Files:**
- Create: `backend/db/__init__.py`
- Create: `backend/db/database.py`
- Create: `backend/db/models.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test for models**

Create `tests/conftest.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()
```

Create `tests/test_models.py`:

```python
from datetime import datetime, timezone

from backend.db.models import Market, Signal, Trade, Position, PnlSnapshot


def test_create_market(db_session):
    market = Market(
        id="market_123",
        condition_id="cond_abc",
        token_id_yes="token_yes_1",
        token_id_no="token_no_1",
        question="Will X happen?",
        slug="will-x-happen",
        category="politics",
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        active=True,
        last_price_yes=0.65,
        last_price_no=0.35,
        volume_24h=50000.0,
        liquidity=25000.0,
    )
    db_session.add(market)
    db_session.commit()

    result = db_session.query(Market).first()
    assert result.id == "market_123"
    assert result.question == "Will X happen?"
    assert result.last_price_yes == 0.65
    assert result.active is True


def test_create_signal(db_session):
    market = Market(
        id="m1",
        condition_id="c1",
        token_id_yes="ty1",
        token_id_no="tn1",
        question="Test?",
        active=True,
    )
    db_session.add(market)
    db_session.commit()

    signal = Signal(
        market_id="m1",
        type="ARBITRAGE",
        source_detail='{"yes_price": 0.45, "no_price": 0.53}',
        current_price=0.45,
        fair_value=0.50,
        edge_pct=2.5,
        confidence=90,
        status="NEW",
    )
    db_session.add(signal)
    db_session.commit()

    result = db_session.query(Signal).first()
    assert result.type == "ARBITRAGE"
    assert result.edge_pct == 2.5
    assert result.market.question == "Test?"


def test_create_trade(db_session):
    market = Market(id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1", question="T?", active=True)
    db_session.add(market)
    db_session.commit()

    trade = Trade(
        market_id="m1",
        token_id="ty1",
        side="BUY",
        price=0.45,
        size=100.0,
        cost=45.90,
        status="FILLED",
        order_id="order_xyz",
    )
    db_session.add(trade)
    db_session.commit()

    result = db_session.query(Trade).first()
    assert result.side == "BUY"
    assert result.cost == 45.90


def test_create_position(db_session):
    market = Market(id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1", question="T?", active=True)
    db_session.add(market)
    db_session.commit()

    pos = Position(
        market_id="m1",
        token_id="ty1",
        side="YES",
        avg_entry_price=0.45,
        size=100.0,
        current_price=0.55,
        unrealized_pnl=10.0,
    )
    db_session.add(pos)
    db_session.commit()

    result = db_session.query(Position).first()
    assert result.unrealized_pnl == 10.0


def test_create_pnl_snapshot(db_session):
    from datetime import date

    snap = PnlSnapshot(
        date=date(2026, 4, 7),
        total_value=5000.0,
        realized_pnl=150.0,
        unrealized_pnl=30.0,
        num_trades=12,
        win_rate=0.58,
    )
    db_session.add(snap)
    db_session.commit()

    result = db_session.query(PnlSnapshot).first()
    assert result.total_value == 5000.0
    assert result.win_rate == 0.58
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.db'`

- [ ] **Step 3: Implement database module**

Create `backend/db/__init__.py`:

```python
```

Create `backend/db/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings

_engine = None
_SessionLocal = None


def get_engine(settings: Settings | None = None):
    global _engine
    if _engine is None:
        if settings is None:
            settings = Settings()
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session_factory(settings: Settings | None = None):
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(settings)
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal


def init_db(settings: Settings | None = None):
    from backend.db.models import Base

    engine = get_engine(settings)
    Base.metadata.create_all(engine)
```

- [ ] **Step 4: Implement ORM models**

Create `backend/db/models.py`:

```python
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    condition_id: Mapped[str] = mapped_column(String, nullable=False)
    token_id_yes: Mapped[str] = mapped_column(String, nullable=False)
    token_id_no: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_price_yes: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_price_no: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    signals: Mapped[list["Signal"]] = relationship(back_populates="market")
    trades: Mapped[list["Trade"]] = relationship(back_populates="market")
    positions: Mapped[list["Position"]] = relationship(back_populates="market")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String, ForeignKey("markets.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    source_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    fair_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    edge_pct: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String, default="NEW")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    market: Mapped["Market"] = relationship(back_populates="signals")
    trades: Mapped[list["Trade"]] = relationship(back_populates="signal")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("signals.id"), nullable=True)
    market_id: Mapped[str] = mapped_column(String, ForeignKey("markets.id"), nullable=False)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    signal: Mapped["Signal | None"] = relationship(back_populates="trades")
    market: Mapped["Market"] = relationship(back_populates="trades")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String, ForeignKey("markets.id"), nullable=False)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    avg_entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    market: Mapped["Market"] = relationship(back_populates="positions")


class PnlSnapshot(Base):
    __tablename__ = "pnl_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    num_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/db/ tests/conftest.py tests/test_models.py
git commit -m "feat: add SQLAlchemy ORM models for markets, signals, trades, positions, pnl"
```

---

### Task 4: Gamma API Client

**Files:**
- Create: `backend/crawler/__init__.py`
- Create: `backend/crawler/gamma_client.py`
- Create: `tests/test_gamma_client.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_gamma_client.py`:

```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from backend.crawler.gamma_client import GammaClient

SAMPLE_EVENT = {
    "id": "event_1",
    "slug": "will-x-win",
    "title": "Will X win?",
    "markets": [
        {
            "id": "market_1",
            "conditionId": "cond_1",
            "question": "Will X win?",
            "slug": "will-x-win",
            "groupItemTitle": "X",
            "active": True,
            "closed": False,
            "clobTokenIds": '["token_yes_1", "token_no_1"]',
            "outcomePrices": '[0.65, 0.35]',
            "volume": "50000",
            "liquidityClob": "25000",
            "endDate": "2026-12-31T00:00:00Z",
            "tags": [{"label": "Politics"}],
        }
    ],
}


@pytest.mark.asyncio
async def test_fetch_active_events():
    mock_response = httpx.Response(200, json=[SAMPLE_EVENT])
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_response):
        client = GammaClient()
        events = await client.fetch_active_events(limit=1)
        assert len(events) == 1
        assert events[0]["id"] == "event_1"


@pytest.mark.asyncio
async def test_parse_markets_from_event():
    client = GammaClient()
    markets = client.parse_markets(SAMPLE_EVENT)
    assert len(markets) == 1
    m = markets[0]
    assert m["id"] == "market_1"
    assert m["condition_id"] == "cond_1"
    assert m["token_id_yes"] == "token_yes_1"
    assert m["token_id_no"] == "token_no_1"
    assert m["question"] == "Will X win?"
    assert m["last_price_yes"] == 0.65
    assert m["last_price_no"] == 0.35
    assert m["category"] == "Politics"
    assert m["active"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_gamma_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.crawler'`

- [ ] **Step 3: Implement Gamma client**

Create `backend/crawler/__init__.py`:

```python
```

Create `backend/crawler/gamma_client.py`:

```python
import json

import httpx

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


class GammaClient:
    def __init__(self, base_url: str = GAMMA_BASE_URL):
        self.base_url = base_url

    async def fetch_active_events(self, limit: int = 100, offset: int = 0) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/events",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "offset": offset,
                    "order": "volume24hr",
                    "ascending": "false",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    def parse_markets(self, event: dict) -> list[dict]:
        results = []
        for m in event.get("markets", []):
            try:
                clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                prices = json.loads(m.get("outcomePrices", "[]"))
            except (json.JSONDecodeError, TypeError):
                continue

            if len(clob_ids) < 2 or len(prices) < 2:
                continue

            tags = m.get("tags", [])
            category = tags[0]["label"] if tags else None

            results.append({
                "id": m["id"],
                "condition_id": m.get("conditionId", ""),
                "token_id_yes": clob_ids[0],
                "token_id_no": clob_ids[1],
                "question": m.get("question", ""),
                "slug": m.get("slug", ""),
                "category": category,
                "end_date": m.get("endDate"),
                "active": m.get("active", True) and not m.get("closed", False),
                "last_price_yes": float(prices[0]),
                "last_price_no": float(prices[1]),
                "volume_24h": float(m.get("volume", 0)),
                "liquidity": float(m.get("liquidityClob", 0)),
            })
        return results
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_gamma_client.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/ tests/test_gamma_client.py
git commit -m "feat: add Gamma API client for market discovery"
```

---

### Task 5: CLOB API Client

**Files:**
- Create: `backend/crawler/clob_client.py`
- Create: `tests/test_clob_client.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_clob_client.py`:

```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from backend.crawler.clob_client import ClobClient

SAMPLE_BOOK = {
    "market": "token_yes_1",
    "asset_id": "token_yes_1",
    "bids": [
        {"price": "0.63", "size": "500"},
        {"price": "0.62", "size": "1000"},
    ],
    "asks": [
        {"price": "0.65", "size": "300"},
        {"price": "0.66", "size": "800"},
    ],
}

SAMPLE_PRICE = {"price": "0.65"}
SAMPLE_MIDPOINT = {"mid": "0.64"}
SAMPLE_SPREAD = {"spread": "0.02"}


@pytest.mark.asyncio
async def test_get_order_book():
    mock_resp = httpx.Response(200, json=SAMPLE_BOOK)
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = ClobClient()
        book = await client.get_order_book("token_yes_1")
        assert book["asset_id"] == "token_yes_1"
        assert len(book["bids"]) == 2
        assert len(book["asks"]) == 2


@pytest.mark.asyncio
async def test_get_price():
    mock_resp = httpx.Response(200, json=SAMPLE_PRICE)
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = ClobClient()
        price = await client.get_price("token_yes_1")
        assert price == 0.65


@pytest.mark.asyncio
async def test_get_midpoint():
    mock_resp = httpx.Response(200, json=SAMPLE_MIDPOINT)
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = ClobClient()
        mid = await client.get_midpoint("token_yes_1")
        assert mid == 0.64


@pytest.mark.asyncio
async def test_get_spread():
    mock_resp = httpx.Response(200, json=SAMPLE_SPREAD)
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = ClobClient()
        spread = await client.get_spread("token_yes_1")
        assert spread == 0.02
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_clob_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.crawler.clob_client'`

- [ ] **Step 3: Implement CLOB client**

Create `backend/crawler/clob_client.py`:

```python
import httpx

CLOB_BASE_URL = "https://clob.polymarket.com"


class ClobClient:
    def __init__(self, base_url: str = CLOB_BASE_URL):
        self.base_url = base_url

    async def get_order_book(self, token_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/book",
                params={"token_id": token_id},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_price(self, token_id: str, side: str = "buy") -> float:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/price",
                params={"token_id": token_id, "side": side},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("price", 0))

    async def get_midpoint(self, token_id: str) -> float:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/midpoint",
                params={"token_id": token_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("mid", 0))

    async def get_spread(self, token_id: str) -> float:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/spread",
                params={"token_id": token_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("spread", 0))

    async def get_prices_batch(self, token_ids: list[str]) -> dict[str, float]:
        results = {}
        async with httpx.AsyncClient() as client:
            for token_id in token_ids:
                try:
                    resp = await client.get(
                        f"{self.base_url}/midpoint",
                        params={"token_id": token_id},
                        timeout=15,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    results[token_id] = float(data.get("mid", 0))
                except (httpx.HTTPError, ValueError):
                    continue
        return results
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_clob_client.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/clob_client.py tests/test_clob_client.py
git commit -m "feat: add CLOB API client for prices and order book"
```

---

### Task 6: Market Crawler (Gamma → DB)

**Files:**
- Create: `backend/crawler/market_crawler.py`
- Create: `tests/test_market_crawler.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_market_crawler.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Market
from backend.crawler.market_crawler import MarketCrawler

PARSED_MARKET = {
    "id": "m1",
    "condition_id": "c1",
    "token_id_yes": "ty1",
    "token_id_no": "tn1",
    "question": "Will X happen?",
    "slug": "will-x-happen",
    "category": "Politics",
    "end_date": "2026-12-31T00:00:00Z",
    "active": True,
    "last_price_yes": 0.65,
    "last_price_no": 0.35,
    "volume_24h": 50000.0,
    "liquidity": 25000.0,
}


@pytest.fixture
def crawler_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_sync_markets_inserts_new(crawler_db):
    mock_event = {"id": "e1", "markets": []}
    with (
        patch.object(
            MarketCrawler, "_fetch_all_events", new_callable=AsyncMock, return_value=[mock_event]
        ),
        patch.object(
            MarketCrawler, "_parse_all_markets", return_value=[PARSED_MARKET]
        ),
    ):
        crawler = MarketCrawler(session=crawler_db)
        count = await crawler.sync_markets()
        assert count == 1

        market = crawler_db.query(Market).first()
        assert market.id == "m1"
        assert market.question == "Will X happen?"
        assert market.last_price_yes == 0.65


@pytest.mark.asyncio
async def test_sync_markets_updates_existing(crawler_db):
    existing = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Will X happen?", active=True, last_price_yes=0.50, last_price_no=0.50,
    )
    crawler_db.add(existing)
    crawler_db.commit()

    updated = {**PARSED_MARKET, "last_price_yes": 0.70, "last_price_no": 0.30}
    with (
        patch.object(MarketCrawler, "_fetch_all_events", new_callable=AsyncMock, return_value=[]),
        patch.object(MarketCrawler, "_parse_all_markets", return_value=[updated]),
    ):
        crawler = MarketCrawler(session=crawler_db)
        count = await crawler.sync_markets()
        assert count == 1

        market = crawler_db.query(Market).first()
        assert market.last_price_yes == 0.70
        assert market.last_price_no == 0.30
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_market_crawler.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.crawler.market_crawler'`

- [ ] **Step 3: Implement MarketCrawler**

Create `backend/crawler/market_crawler.py`:

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.crawler.gamma_client import GammaClient
from backend.db.models import Market


class MarketCrawler:
    def __init__(self, session: Session, gamma_client: GammaClient | None = None):
        self.session = session
        self.gamma = gamma_client or GammaClient()

    async def _fetch_all_events(self, max_pages: int = 5) -> list[dict]:
        all_events = []
        for page in range(max_pages):
            events = await self.gamma.fetch_active_events(limit=100, offset=page * 100)
            if not events:
                break
            all_events.extend(events)
        return all_events

    def _parse_all_markets(self, events: list[dict]) -> list[dict]:
        all_markets = []
        for event in events:
            all_markets.extend(self.gamma.parse_markets(event))
        return all_markets

    async def sync_markets(self) -> int:
        events = await self._fetch_all_events()
        parsed = self._parse_all_markets(events)
        count = 0

        for data in parsed:
            existing = self.session.get(Market, data["id"])
            if existing:
                existing.last_price_yes = data["last_price_yes"]
                existing.last_price_no = data["last_price_no"]
                existing.volume_24h = data["volume_24h"]
                existing.liquidity = data["liquidity"]
                existing.active = data["active"]
                existing.updated_at = datetime.now(timezone.utc)
            else:
                end_date = None
                if data.get("end_date"):
                    try:
                        end_date = datetime.fromisoformat(data["end_date"].replace("Z", "+00:00"))
                    except ValueError:
                        pass

                market = Market(
                    id=data["id"],
                    condition_id=data["condition_id"],
                    token_id_yes=data["token_id_yes"],
                    token_id_no=data["token_id_no"],
                    question=data["question"],
                    slug=data.get("slug"),
                    category=data.get("category"),
                    end_date=end_date,
                    active=data["active"],
                    last_price_yes=data["last_price_yes"],
                    last_price_no=data["last_price_no"],
                    volume_24h=data["volume_24h"],
                    liquidity=data["liquidity"],
                )
                self.session.add(market)
            count += 1

        self.session.commit()
        return count
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_market_crawler.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/market_crawler.py tests/test_market_crawler.py
git commit -m "feat: add MarketCrawler to sync markets from Gamma API to DB"
```

---

### Task 7: Price Crawler (CLOB → DB)

**Files:**
- Create: `backend/crawler/price_crawler.py`
- Create: `tests/test_price_crawler.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_price_crawler.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Market
from backend.crawler.price_crawler import PriceCrawler


@pytest.fixture
def price_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    m = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True, last_price_yes=0.50, last_price_no=0.50,
    )
    session.add(m)
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_update_prices(price_db):
    mock_prices = {"ty1": 0.65, "tn1": 0.35}
    with patch(
        "backend.crawler.price_crawler.ClobClient.get_prices_batch",
        new_callable=AsyncMock,
        return_value=mock_prices,
    ):
        crawler = PriceCrawler(session=price_db)
        updated = await crawler.update_prices()
        assert updated == 1

        market = price_db.query(Market).first()
        assert market.last_price_yes == 0.65
        assert market.last_price_no == 0.35


@pytest.mark.asyncio
async def test_update_prices_skips_inactive(price_db):
    market = price_db.query(Market).first()
    market.active = False
    price_db.commit()

    with patch(
        "backend.crawler.price_crawler.ClobClient.get_prices_batch",
        new_callable=AsyncMock,
        return_value={},
    ):
        crawler = PriceCrawler(session=price_db)
        updated = await crawler.update_prices()
        assert updated == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_price_crawler.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.crawler.price_crawler'`

- [ ] **Step 3: Implement PriceCrawler**

Create `backend/crawler/price_crawler.py`:

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.crawler.clob_client import ClobClient
from backend.db.models import Market


class PriceCrawler:
    def __init__(self, session: Session, clob_client: ClobClient | None = None):
        self.session = session
        self.clob = clob_client or ClobClient()

    async def update_prices(self) -> int:
        markets = self.session.query(Market).filter(Market.active == True).all()
        if not markets:
            return 0

        token_ids = []
        token_to_market: dict[str, tuple[Market, str]] = {}
        for m in markets:
            token_ids.append(m.token_id_yes)
            token_ids.append(m.token_id_no)
            token_to_market[m.token_id_yes] = (m, "yes")
            token_to_market[m.token_id_no] = (m, "no")

        prices = await self.clob.get_prices_batch(token_ids)

        updated_markets = set()
        for token_id, price in prices.items():
            if token_id in token_to_market:
                market, side = token_to_market[token_id]
                if side == "yes":
                    market.last_price_yes = price
                else:
                    market.last_price_no = price
                market.updated_at = datetime.now(timezone.utc)
                updated_markets.add(market.id)

        self.session.commit()
        return len(updated_markets)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_price_crawler.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/price_crawler.py tests/test_price_crawler.py
git commit -m "feat: add PriceCrawler to update market prices from CLOB API"
```

---

### Task 8: Signal Engine Base Class

**Files:**
- Create: `backend/signals/__init__.py`
- Create: `backend/signals/base.py`

- [ ] **Step 1: Implement signal base class**

Create `backend/signals/__init__.py`:

```python
```

Create `backend/signals/base.py`:

```python
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from backend.db.models import Signal


class SignalDetector(ABC):
    def __init__(self, session: Session):
        self.session = session

    @abstractmethod
    def detect(self) -> list[Signal]:
        """Scan markets and return a list of new Signal objects (not yet committed)."""
        ...

    def save_signals(self, signals: list[Signal]) -> int:
        for signal in signals:
            self.session.add(signal)
        self.session.commit()
        return len(signals)
```

- [ ] **Step 2: Commit**

```bash
git add backend/signals/
git commit -m "feat: add SignalDetector base class"
```

---

### Task 9: Arbitrage Signal Detector

**Files:**
- Create: `backend/signals/arbitrage.py`
- Create: `tests/test_arbitrage.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_arbitrage.py`:

```python
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings
from backend.db.models import Base, Market, Signal
from backend.signals.arbitrage import ArbitrageDetector


@pytest.fixture
def arb_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def test_detects_yes_no_mispricing(arb_db):
    """YES + NO < 1.0 means buying both locks profit."""
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.45, last_price_no=0.50,  # sum = 0.95, gap = 5%
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()

    assert len(signals) == 1
    s = signals[0]
    assert s.type == "ARBITRAGE"
    assert s.market_id == "m1"
    assert s.edge_pct > 0
    detail = json.loads(s.source_detail)
    assert detail["yes_price"] == 0.45
    assert detail["no_price"] == 0.50


def test_no_signal_when_fairly_priced(arb_db):
    """YES + NO = 1.0 means no arbitrage."""
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.60, last_price_no=0.40,  # sum = 1.0
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()

    assert len(signals) == 0


def test_no_signal_when_edge_too_small(arb_db):
    """Edge exists but is smaller than fee + min_edge threshold."""
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.49, last_price_no=0.50,  # sum = 0.99, gap = 1%
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()

    assert len(signals) == 0


def test_skips_inactive_markets(arb_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=False,
        last_price_yes=0.30, last_price_no=0.30,
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()

    assert len(signals) == 0


def test_saves_signals(arb_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.40, last_price_no=0.45,
    )
    arb_db.add(market)
    arb_db.commit()

    settings = Settings(POLYMARKET_FEE_PCT=2.0, RISK_MIN_EDGE_PCT=1.0)
    detector = ArbitrageDetector(session=arb_db, settings=settings)
    signals = detector.detect()
    count = detector.save_signals(signals)

    assert count == 1
    saved = arb_db.query(Signal).first()
    assert saved.status == "NEW"
    assert saved.type == "ARBITRAGE"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_arbitrage.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.signals.arbitrage'`

- [ ] **Step 3: Implement ArbitrageDetector**

Create `backend/signals/arbitrage.py`:

```python
import json

from sqlalchemy.orm import Session

from backend.config import Settings
from backend.db.models import Market, Signal
from backend.signals.base import SignalDetector


class ArbitrageDetector(SignalDetector):
    def __init__(self, session: Session, settings: Settings | None = None):
        super().__init__(session)
        self.settings = settings or Settings()

    def detect(self) -> list[Signal]:
        markets = (
            self.session.query(Market)
            .filter(
                Market.active == True,
                Market.last_price_yes.isnot(None),
                Market.last_price_no.isnot(None),
            )
            .all()
        )

        signals = []
        for market in markets:
            signal = self._check_yes_no_arb(market)
            if signal:
                signals.append(signal)
        return signals

    def _check_yes_no_arb(self, market: Market) -> Signal | None:
        yes_price = market.last_price_yes
        no_price = market.last_price_no
        total_cost = yes_price + no_price

        # If total < 1.0, buying both YES and NO guarantees profit of (1.0 - total)
        # If total > 1.0, selling both (if possible) could profit, but harder on Polymarket
        if total_cost >= 1.0:
            return None

        gap = 1.0 - total_cost
        gross_edge_pct = (gap / total_cost) * 100
        net_edge_pct = gross_edge_pct - self.settings.POLYMARKET_FEE_PCT

        if net_edge_pct < self.settings.RISK_MIN_EDGE_PCT:
            return None

        return Signal(
            market_id=market.id,
            type="ARBITRAGE",
            source_detail=json.dumps({
                "yes_price": yes_price,
                "no_price": no_price,
                "total_cost": round(total_cost, 4),
                "gross_edge_pct": round(gross_edge_pct, 2),
                "net_edge_pct": round(net_edge_pct, 2),
                "strategy": "buy_both",
            }),
            current_price=yes_price,
            fair_value=1.0 - no_price,
            edge_pct=round(net_edge_pct, 2),
            confidence=95,
            status="NEW",
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_arbitrage.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/signals/arbitrage.py tests/test_arbitrage.py
git commit -m "feat: add ArbitrageDetector for YES/NO mispricing signals"
```

---

### Task 10: Price Anomaly Signal Detector

**Files:**
- Create: `backend/signals/anomaly.py`
- Create: `tests/test_anomaly.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_anomaly.py`:

```python
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Market, Signal
from backend.signals.anomaly import AnomalyDetector


@pytest.fixture
def anomaly_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def make_price_history(mean: float, count: int = 50, std: float = 0.02) -> list[dict]:
    """Generate synthetic price history around a mean."""
    import random
    random.seed(42)
    return [
        {"t": i, "p": round(mean + random.gauss(0, std), 4)}
        for i in range(count)
    ]


def test_detects_price_spike(anomaly_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.85,  # way above mean of ~0.50
        last_price_no=0.15,
        volume_24h=100000,
    )
    anomaly_db.add(market)
    anomaly_db.commit()

    history = make_price_history(mean=0.50, count=50, std=0.02)
    detector = AnomalyDetector(session=anomaly_db, sigma_threshold=2.0, min_volume=1000)
    signals = detector.detect(price_histories={"m1": history})

    assert len(signals) == 1
    s = signals[0]
    assert s.type == "PRICE_ANOMALY"
    assert s.market_id == "m1"
    detail = json.loads(s.source_detail)
    assert "z_score" in detail
    assert abs(detail["z_score"]) > 2.0


def test_no_signal_when_price_normal(anomaly_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.51,  # very close to mean
        last_price_no=0.49,
        volume_24h=100000,
    )
    anomaly_db.add(market)
    anomaly_db.commit()

    history = make_price_history(mean=0.50, count=50, std=0.02)
    detector = AnomalyDetector(session=anomaly_db, sigma_threshold=2.0, min_volume=1000)
    signals = detector.detect(price_histories={"m1": history})

    assert len(signals) == 0


def test_no_signal_when_low_volume(anomaly_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.85,
        last_price_no=0.15,
        volume_24h=500,  # below min_volume threshold
    )
    anomaly_db.add(market)
    anomaly_db.commit()

    history = make_price_history(mean=0.50, count=50, std=0.02)
    detector = AnomalyDetector(session=anomaly_db, sigma_threshold=2.0, min_volume=1000)
    signals = detector.detect(price_histories={"m1": history})

    assert len(signals) == 0


def test_no_signal_when_insufficient_history(anomaly_db):
    market = Market(
        id="m1", condition_id="c1", token_id_yes="ty1", token_id_no="tn1",
        question="Test?", active=True,
        last_price_yes=0.85, last_price_no=0.15,
        volume_24h=100000,
    )
    anomaly_db.add(market)
    anomaly_db.commit()

    history = make_price_history(mean=0.50, count=3, std=0.02)  # too few
    detector = AnomalyDetector(session=anomaly_db, sigma_threshold=2.0, min_volume=1000)
    signals = detector.detect(price_histories={"m1": history})

    assert len(signals) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_anomaly.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.signals.anomaly'`

- [ ] **Step 3: Implement AnomalyDetector**

Create `backend/signals/anomaly.py`:

```python
import json
import statistics

from sqlalchemy.orm import Session

from backend.db.models import Market, Signal
from backend.signals.base import SignalDetector


class AnomalyDetector(SignalDetector):
    def __init__(
        self,
        session: Session,
        sigma_threshold: float = 2.0,
        min_volume: float = 1000.0,
        min_history: int = 10,
    ):
        super().__init__(session)
        self.sigma_threshold = sigma_threshold
        self.min_volume = min_volume
        self.min_history = min_history

    def detect(self, price_histories: dict[str, list[dict]]) -> list[Signal]:
        markets = (
            self.session.query(Market)
            .filter(Market.active == True, Market.last_price_yes.isnot(None))
            .all()
        )

        signals = []
        for market in markets:
            history = price_histories.get(market.id, [])
            signal = self._check_anomaly(market, history)
            if signal:
                signals.append(signal)
        return signals

    def _check_anomaly(self, market: Market, history: list[dict]) -> Signal | None:
        if len(history) < self.min_history:
            return None

        if (market.volume_24h or 0) < self.min_volume:
            return None

        prices = [h["p"] for h in history]
        mean = statistics.mean(prices)
        stdev = statistics.stdev(prices)

        if stdev == 0:
            return None

        current = market.last_price_yes
        z_score = (current - mean) / stdev

        if abs(z_score) < self.sigma_threshold:
            return None

        edge_pct = abs(current - mean) / mean * 100

        return Signal(
            market_id=market.id,
            type="PRICE_ANOMALY",
            source_detail=json.dumps({
                "current_price": current,
                "mean_price": round(mean, 4),
                "stdev": round(stdev, 4),
                "z_score": round(z_score, 2),
                "direction": "UP" if z_score > 0 else "DOWN",
                "volume_24h": market.volume_24h,
            }),
            current_price=current,
            fair_value=round(mean, 4),
            edge_pct=round(edge_pct, 2),
            confidence=min(int(abs(z_score) * 25), 100),
            status="NEW",
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_anomaly.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/signals/anomaly.py tests/test_anomaly.py
git commit -m "feat: add AnomalyDetector for price deviation signals"
```

---

### Task 11: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
pytest -v
```

Expected: All 20 tests pass (2 config + 5 models + 2 gamma + 4 clob + 2 market_crawler + 2 price_crawler + 5 arbitrage + 4 anomaly = 26 tests).

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "chore: Plan A complete - backend core with crawlers and signal engine"
```

---

## Verification Checklist

After all tasks are complete, verify:

1. `pytest -v` — all tests pass
2. `python -c "from backend.config import Settings; print(Settings())"` — config loads
3. `python -c "from backend.db.models import Base; print(Base.metadata.tables.keys())"` — all 5 tables present
4. `python -c "from backend.signals.arbitrage import ArbitrageDetector; print('OK')"` — imports clean
5. `python -c "from backend.signals.anomaly import AnomalyDetector; print('OK')"` — imports clean
