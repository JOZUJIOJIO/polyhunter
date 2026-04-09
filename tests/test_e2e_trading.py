"""
端到端交易流程集成测试
信号检测 → 风控检查 → 下单执行 → 仓位更新 → PnL 快照
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from backend.config import Settings
from backend.db.models import Market, Signal, Trade, Position
from backend.signals.arbitrage import ArbitrageDetector
from backend.trader.risk_manager import RiskManager
from backend.trader.executor import OrderExecutor
from backend.trader.position_tracker import PositionTracker


def _make_settings(**overrides):
    """创建测试 Settings，不读 .env"""
    defaults = {
        "POLYMARKET_PRIVATE_KEY": "0x" + "a" * 64,
        "POLYMARKET_API_KEY": "test",
        "POLYMARKET_API_SECRET": "test",
        "POLYMARKET_API_PASSPHRASE": "test",
        "POLYMARKET_FUNDER": "0x" + "b" * 40,
        "OPENROUTER_API_KEY": "test",
        "POLYMARKET_FEE_PCT": 2.0,
        "RISK_MIN_EDGE_PCT": 1.0,
        "RISK_MAX_SINGLE_BET_PCT": 10,
        "RISK_MAX_DAILY_LOSS_PCT": 5,
        "RISK_MAX_POSITION_PCT": 20,
        "RISK_MAX_POSITIONS": 10,
        "RISK_EXPIRY_BUFFER_HOURS": 24,
    }
    defaults.update(overrides)
    return Settings.model_construct(**defaults)


def _add_arb_market(session, market_id="m1", yes_price=0.45, no_price=0.45):
    """添加一个有套利机会的市场"""
    market = Market(
        id=market_id,
        condition_id="cond1",
        token_id_yes="token_yes_1",
        token_id_no="token_no_1",
        question="Will BTC hit 100k?",
        category="crypto",
        active=True,
        last_price_yes=yes_price,
        last_price_no=no_price,
        liquidity=10000.0,
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(market)
    session.commit()
    return market


class TestE2EArbitrageToExecution:
    """测试完整套利交易链路"""

    def test_full_arb_pipeline(self, db_session):
        """信号检测 → 风控 → 下单 → 仓位创建"""
        settings = _make_settings()

        # 1. 创建有套利机会的市场 (YES=0.45, NO=0.45, total=0.90, edge=11.1%-2%=9.1%)
        market = _add_arb_market(db_session)

        # 2. 检测套利信号
        detector = ArbitrageDetector(db_session, settings)
        signals = detector.detect()
        assert len(signals) == 1
        signal = signals[0]
        assert signal.type == "ARBITRAGE"
        assert signal.edge_pct > 1.0
        assert signal.confidence == 95

        # 持久化信号
        db_session.add(signal)
        db_session.commit()

        # 3. 风控 + 下单
        rm = RiskManager(session=db_session, settings=settings, total_balance=100.0)
        executor = OrderExecutor(session=db_session, risk_manager=rm, settings=settings)

        with patch.object(executor, "_submit_order", return_value="order_123"):
            trade = executor.execute(
                signal_id=signal.id,
                market_id=market.id,
                token_id=market.token_id_yes,
                side="BUY",
                price=0.45,
                size=5.0,
            )

        # 4. 验证交易
        assert trade is not None
        assert trade.status == "FILLED"
        assert trade.order_id == "order_123"
        assert trade.price == 0.45
        assert trade.size == 5.0

        # 5. 信号状态更新
        db_session.refresh(signal)
        assert signal.status == "ACTED"

        # 6. 更新仓位
        tracker = PositionTracker(session=db_session, total_balance=100.0)
        position = tracker.update_from_trade(trade)
        assert position is not None
        assert position.side == "YES"
        assert position.avg_entry_price == 0.45
        assert position.size == 5.0

    def test_arb_signal_rejected_by_risk(self, db_session):
        """信号被风控拒绝 → 不执行"""
        settings = _make_settings(RISK_MAX_SINGLE_BET_PCT=1)  # 极低上限

        market = _add_arb_market(db_session)
        detector = ArbitrageDetector(db_session, settings)
        signals = detector.detect()
        assert len(signals) == 1

        signal = signals[0]
        db_session.add(signal)
        db_session.commit()

        rm = RiskManager(session=db_session, settings=settings, total_balance=10.0)
        executor = OrderExecutor(session=db_session, risk_manager=rm, settings=settings)

        # 5.0 * 0.45 = 2.25, 超过 10 * 1% = 0.10
        trade = executor.execute(
            signal_id=signal.id,
            market_id=market.id,
            token_id=market.token_id_yes,
            side="BUY",
            price=0.45,
            size=5.0,
        )

        assert trade is None
        # 无持仓
        positions = db_session.query(Position).all()
        assert len(positions) == 0

    def test_no_arb_when_prices_fair(self, db_session):
        """市场价格公允时不产生套利信号"""
        settings = _make_settings()
        _add_arb_market(db_session, yes_price=0.55, no_price=0.50)  # total=1.05

        detector = ArbitrageDetector(db_session, settings)
        signals = detector.detect()
        assert len(signals) == 0

    def test_submission_failure_creates_cancelled_trade(self, db_session):
        """下单失败 → trade 状态为 CANCELLED"""
        settings = _make_settings()
        market = _add_arb_market(db_session)

        detector = ArbitrageDetector(db_session, settings)
        signals = detector.detect()
        signal = signals[0]
        db_session.add(signal)
        db_session.commit()

        rm = RiskManager(session=db_session, settings=settings, total_balance=100.0)
        executor = OrderExecutor(session=db_session, risk_manager=rm, settings=settings)

        with patch.object(executor, "_submit_order", side_effect=Exception("Network timeout")):
            trade = executor.execute(
                signal_id=signal.id,
                market_id=market.id,
                token_id=market.token_id_yes,
                side="BUY",
                price=0.45,
                size=5.0,
            )

        assert trade is not None
        assert trade.status == "CANCELLED"


class TestE2EPositionLifecycle:
    """测试仓位完整生命周期：开仓 → 加仓 → 平仓"""

    def test_open_add_close_position(self, db_session):
        settings = _make_settings()
        market = _add_arb_market(db_session)
        rm = RiskManager(session=db_session, settings=settings, total_balance=100.0)
        executor = OrderExecutor(session=db_session, risk_manager=rm, settings=settings)
        tracker = PositionTracker(session=db_session, total_balance=100.0)

        with patch.object(executor, "_submit_order", return_value="order_1"):
            # 1. 开仓：买入 5 份 @ 0.45
            trade1 = executor.execute(
                signal_id=None,
                market_id=market.id,
                token_id=market.token_id_yes,
                side="BUY",
                price=0.45,
                size=5.0,
            )
            pos = tracker.update_from_trade(trade1)
            assert pos.size == 5.0
            assert pos.avg_entry_price == 0.45

        with patch.object(executor, "_submit_order", return_value="order_2"):
            # 2. 加仓：再买 3 份 @ 0.50
            trade2 = executor.execute(
                signal_id=None,
                market_id=market.id,
                token_id=market.token_id_yes,
                side="BUY",
                price=0.50,
                size=3.0,
            )
            pos = tracker.update_from_trade(trade2)
            assert pos.size == 8.0
            # 加权均价 = (5*0.45 + 3*0.50) / 8 = 3.75/8 = 0.46875
            assert abs(pos.avg_entry_price - 0.46875) < 0.001

        with patch.object(executor, "_submit_order", return_value="order_3"):
            # 3. 平仓：卖出 8 份
            trade3 = executor.execute(
                signal_id=None,
                market_id=market.id,
                token_id=market.token_id_yes,
                side="SELL",
                price=0.60,
                size=8.0,
            )
            tracker.update_from_trade(trade3)

        # 平仓后仓位应被删除
        remaining = db_session.query(Position).filter(
            Position.market_id == market.id
        ).all()
        assert len(remaining) == 0


class TestE2EPnLTracking:
    """测试 PnL 快照"""

    def test_snapshot_after_trades(self, db_session):
        settings = _make_settings()
        market = _add_arb_market(db_session, yes_price=0.45, no_price=0.45)
        rm = RiskManager(session=db_session, settings=settings, total_balance=100.0)
        executor = OrderExecutor(session=db_session, risk_manager=rm, settings=settings)
        tracker = PositionTracker(session=db_session, total_balance=100.0)

        with patch.object(executor, "_submit_order", return_value="order_1"):
            trade = executor.execute(
                signal_id=None,
                market_id=market.id,
                token_id=market.token_id_yes,
                side="BUY",
                price=0.45,
                size=10.0,
            )
            tracker.update_from_trade(trade)

        # 模拟价格上涨
        market.last_price_yes = 0.60
        db_session.commit()

        # 刷新 PnL
        tracker.refresh_pnl()

        pos = db_session.query(Position).first()
        assert pos.current_price == 0.60
        # unrealized = (0.60 - 0.45) * 10 = 1.50
        assert abs(pos.unrealized_pnl - 1.50) < 0.01

        # 拍快照
        snapshot = tracker.take_snapshot()
        assert abs(snapshot.unrealized_pnl - 1.50) < 0.01
        assert snapshot.num_trades == 1
