import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from trading_bot.simulation.risk_manager import RiskCheck, RiskConfig, RiskManager


def test_defaults_are_conservative():
    rm = RiskManager()
    assert rm.config.max_position_pct == pytest.approx(0.05)
    assert rm.config.max_risk_per_trade == pytest.approx(0.01)
    assert rm.config.daily_loss_limit == pytest.approx(0.03)
    assert rm.config.max_open_positions == 1


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        RiskConfig(max_position_pct=0).validate()
    with pytest.raises(ValueError):
        RiskConfig(max_risk_per_trade=-0.1).validate()
    with pytest.raises(ValueError):
        RiskConfig(daily_loss_limit=2.0).validate()
    with pytest.raises(ValueError):
        RiskConfig(stop_loss_pct=0).validate()
    with pytest.raises(ValueError):
        RiskConfig(max_open_positions=0).validate()


def test_position_sizing_risk_based():
    rm = RiskManager(RiskConfig(max_position_pct=1.0, max_risk_per_trade=0.01))
    # Equity 10000, risk 1% = 100. Entry 100, stop 98 -> risk/unit = 2.
    result = rm.size_position(10000.0, 100.0, 98.0)
    assert result.allowed
    assert result.details["quantity"] == pytest.approx(50.0)
    assert result.details["risk_at_stop"] == pytest.approx(100.0)
    assert result.details["capped_by"] == "risk"


def test_position_sizing_capped_by_notional():
    rm = RiskManager(RiskConfig(max_position_pct=0.05, max_risk_per_trade=0.5))
    # Risk budget huge -> notional cap binds: 5% of 10000 = 500 / 100 = 5 units.
    result = rm.size_position(10000.0, 100.0, 99.0)
    assert result.allowed
    assert result.details["capped_by"] == "notional"
    assert result.details["quantity"] == pytest.approx(5.0)


def test_position_sizing_invalid_inputs():
    rm = RiskManager()
    assert not rm.size_position(10000.0, 100.0, 100.0)
    assert not rm.size_position(0, 100.0, 98.0)
    assert not rm.size_position(10000.0, 0, 98.0)


def test_daily_loss_limit_triggers_and_blocks():
    rm = RiskManager(RiskConfig(daily_loss_limit=0.03))
    rm.daily_start_equity = 10000.0
    rm.current_day = "2020-01-01"
    rm.roll_day_if_needed(10000.0, today="2020-01-01")
    rm.daily_start_equity = 10000.0
    assert rm.check_daily_limit(9800.0)          # 2% loss ok
    assert not rm.check_daily_limit(9600.0)      # 4% loss blocked
    assert rm.daily_loss(9600.0) == pytest.approx(400.0)
    assert rm.remaining_daily_allowance(9600.0) == pytest.approx(0.0)


def test_remaining_allowance_positive_when_flat():
    rm = RiskManager(RiskConfig(daily_loss_limit=0.03))
    rm.daily_start_equity = 10000.0
    assert rm.remaining_daily_allowance(10000.0) == pytest.approx(300.0)
    assert rm.remaining_daily_allowance(9900.0) == pytest.approx(200.0)


def test_consecutive_losses_trigger():
    rm = RiskManager(RiskConfig(max_consecutive_losses=3))
    rm.record_realized(-10)
    rm.record_realized(-10)
    assert rm.check_consecutive_losses().allowed
    rm.record_realized(-10)
    assert not rm.check_consecutive_losses()
    rm.record_realized(5)  # a win resets the counter
    assert rm.consecutive_losses == 0


def test_evaluate_new_trade_limits():
    rm = RiskManager(RiskConfig(max_open_positions=1, max_total_exposure_pct=0.5))
    assert not rm.evaluate_new_trade(10000.0, open_positions=1, current_exposure=0, trade_notional=100)
    assert not rm.evaluate_new_trade(10000.0, open_positions=0, current_exposure=5000.0, trade_notional=100)


def test_state_roundtrip_persists_lockout():
    rm = RiskManager(RiskConfig(max_consecutive_losses=1))
    rm.record_realized(-5)
    rm.trigger_emergency_pause("test")
    state = rm.to_state()

    restored = RiskManager()
    restored.load_state(state)
    assert restored.emergency_pause is True
    assert restored.consecutive_losses == 1


def test_reset_lockouts_audited():
    rm = RiskManager()
    rm.trigger_emergency_pause("test")
    rm.reset_lockouts("unit_test")
    assert rm.emergency_pause is False
    assert any(e["event"] == "reset_lockouts" for e in rm.lockout_events)