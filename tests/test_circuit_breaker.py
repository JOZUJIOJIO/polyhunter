"""熔断机制测试"""

from datetime import datetime, timezone, timedelta

from backend.config import Settings
from backend.db.models import Market, Trade, Position
from backend.trader.risk_manager import RiskManager


def _settings(**overrides):
    defaults = {
        "RISK_MAX_SINGLE_BET_PCT": 10,
        "RISK_MAX_DAILY_LOSS_PCT": 5,
        "RISK_MAX_POSITION_PCT": 20,
        "RISK_MAX_POSITIONS": 10,
        "RISK_EXPIRY_BUFFER_HOURS": 24,
        "CIRCUIT_BREAKER_CONSECUTIVE_LOSSES": 3,
        "CIRCUIT_BREAKER_COOLDOWN_MINUTES": 60,
    }
    defaults.update(overrides)
    return Settings.model_construct(**defaults)


def _add_market(session, market_id="m1"):
    market = Market(
        id=market_id,
        condition_id="c1",
        token_id_yes="ty",
        token_id_no="tn",
        question="Test?",
        category="test",
        active=True,
        last_price_yes=0.50,
        last_price_no=0.50,
        liquidity=1000,
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(market)
    session.commit()
    return market


def _add_losing_trades(session, count, market_id="m1"):
    """添加 N 笔亏损交易"""
    for i in range(count):
        trade = Trade(
            market_id=market_id,
            token_id="ty",
            side="BUY",
            price=0.50,
            size=10.0,
            cost=5.0,
            status="FILLED",
            pnl=-1.0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=count - i),
        )
        session.add(trade)
    session.commit()


def _add_winning_trade(session, market_id="m1"):
    """添加 1 笔盈利交易"""
    trade = Trade(
        market_id=market_id,
        token_id="ty",
        side="BUY",
        price=0.50,
        size=10.0,
        cost=5.0,
        status="FILLED",
        pnl=2.0,
        created_at=datetime.now(timezone.utc),
    )
    session.add(trade)
    session.commit()


class TestCircuitBreaker:
    def test_no_trades_allows_order(self, db_session):
        """无历史交易 → 不熔断"""
        _add_market(db_session)
        rm = RiskManager(db_session, _settings(), total_balance=100.0)
        result = rm.check_order("m1", "BUY", 1.0, 0.50)
        assert result.approved

    def test_fewer_losses_than_threshold(self, db_session):
        """亏损次数不够 → 不熔断"""
        _add_market(db_session)
        _add_losing_trades(db_session, 2)  # 阈值是 3
        rm = RiskManager(db_session, _settings(), total_balance=100.0)
        result = rm.check_order("m1", "BUY", 1.0, 0.50)
        assert result.approved

    def test_consecutive_losses_triggers_breaker(self, db_session):
        """连续 3 笔亏损 → 熔断"""
        _add_market(db_session)
        _add_losing_trades(db_session, 3)
        rm = RiskManager(db_session, _settings(), total_balance=100.0)
        result = rm.check_order("m1", "BUY", 1.0, 0.50)
        assert not result.approved
        assert "Circuit breaker" in result.reason
        assert "consecutive losses" in result.reason

    def test_win_breaks_losing_streak(self, db_session):
        """连续亏损后有一笔盈利 → 不熔断"""
        _add_market(db_session)
        _add_losing_trades(db_session, 3)
        _add_winning_trade(db_session)  # 打断连续亏损
        rm = RiskManager(db_session, _settings(), total_balance=100.0)
        result = rm.check_order("m1", "BUY", 1.0, 0.50)
        assert result.approved

    def test_cooldown_blocks_during_period(self, db_session):
        """熔断后在冷却期内 → 继续阻止"""
        _add_market(db_session)
        _add_losing_trades(db_session, 3)
        rm = RiskManager(db_session, _settings(), total_balance=100.0)

        # 第一次触发熔断
        result1 = rm.check_order("m1", "BUY", 1.0, 0.50)
        assert not result1.approved

        # 第二次仍在冷却期内
        result2 = rm.check_order("m1", "BUY", 1.0, 0.50)
        assert not result2.approved
        assert "cooling down" in result2.reason

    def test_cooldown_expires_allows_trading(self, db_session):
        """冷却期结束后 → 恢复交易（如果没有新的连续亏损）"""
        _add_market(db_session)
        _add_losing_trades(db_session, 3)
        rm = RiskManager(db_session, _settings(CIRCUIT_BREAKER_COOLDOWN_MINUTES=60), total_balance=100.0)

        # 触发熔断
        rm.check_order("m1", "BUY", 1.0, 0.50)

        # 模拟冷却期结束
        rm._circuit_tripped_at = datetime.now(timezone.utc) - timedelta(minutes=61)

        # 添加一笔盈利打断亏损序列
        _add_winning_trade(db_session)

        result = rm.check_order("m1", "BUY", 1.0, 0.50)
        assert result.approved

    def test_is_circuit_breaker_active(self, db_session):
        """查询接口"""
        _add_market(db_session)
        _add_losing_trades(db_session, 3)
        rm = RiskManager(db_session, _settings(), total_balance=100.0)

        assert rm.is_circuit_breaker_active()

    def test_custom_threshold(self, db_session):
        """自定义连续亏损阈值"""
        _add_market(db_session)
        _add_losing_trades(db_session, 5)

        # 阈值 = 10，5 笔亏损不够
        rm = RiskManager(db_session, _settings(CIRCUIT_BREAKER_CONSECUTIVE_LOSSES=10), total_balance=100.0)
        result = rm.check_order("m1", "BUY", 1.0, 0.50)
        assert result.approved
