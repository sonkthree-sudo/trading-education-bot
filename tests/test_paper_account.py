import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from trading_bot.simulation.paper_account import PaperAccount
from trading_bot.simulation.risk_manager import RiskConfig, RiskManager


def make_account(**kwargs):
    return PaperAccount(initial_balance=10000.0, **kwargs)


def test_initial_balance():
    acc = make_account()
    assert acc.balance == 10000.0
    assert acc.get_equity() == 10000.0


def test_invalid_initial_balance():
    with pytest.raises(ValueError):
        PaperAccount(initial_balance=0)


def test_long_pnl_profit():
    acc = make_account(commission_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    pos = acc.open_position("BTC/USDT", "crypto", "LONG", 1.0, 100.0)
    pnl = acc.close_position(pos.id, 110.0)
    assert pnl == pytest.approx(10.0)


def test_short_pnl_profit():
    acc = make_account(commission_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    pos = acc.open_position("BTC/USDT", "crypto", "SHORT", 1.0, 100.0)
    pnl = acc.close_position(pos.id, 90.0)
    assert pnl == pytest.approx(10.0)


def test_short_pnl_loss():
    acc = make_account(commission_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    pos = acc.open_position("BTC/USDT", "crypto", "SHORT", 1.0, 100.0)
    pnl = acc.close_position(pos.id, 115.0)
    assert pnl == pytest.approx(-15.0)


def test_commission_reduces_pnl():
    acc = make_account(commission_pct=0.001, slippage_pct=0.0, spread_pct=0.0)
    pos = acc.open_position("BTC/USDT", "crypto", "LONG", 1.0, 100.0)
    pnl = acc.close_position(pos.id, 110.0)
    # Entry fee 0.1 + exit fee 0.11 = 0.21
    assert pnl == pytest.approx(10.0 - 0.21, abs=1e-6)


def test_spread_and_slippage_are_adverse():
    acc = make_account(commission_pct=0.0, slippage_pct=0.001, spread_pct=0.001)
    pos = acc.open_position("BTC/USDT", "crypto", "LONG", 1.0, 100.0)
    # Entry fill should be above 100.
    assert pos.entry_price > 100.0
    pnl = acc.close_position(pos.id, 100.0)
    # Even though mark price returned to 100, costs make the trade a loss.
    assert pnl < 0


def test_duplicate_position_prevented():
    acc = make_account()
    acc.open_position("BTC/USDT", "crypto", "LONG", 0.1, 100.0)
    with pytest.raises(ValueError):
        acc.open_position("BTC/USDT", "crypto", "LONG", 0.1, 100.0)


def test_invalid_quantity_and_price_rejected():
    acc = make_account()
    assert not acc.validate_order("BTC/USDT", "LONG", 0, 100.0)
    assert not acc.validate_order("BTC/USDT", "LONG", 0.1, 0)
    assert not acc.validate_order("BTC/USDT", "SIDEWAYS", 0.1, 100.0)


def test_max_position_size_enforced():
    acc = make_account()
    # 5% of 10000 = 500 notional; requesting 10 units at 100 = 1000 notional.
    check = acc.validate_order("BTC/USDT", "LONG", 10.0, 100.0)
    assert not check
    assert "position" in check.reason.lower() or "exposure" in check.reason.lower()


def test_equity_tracks_unrealized():
    acc = make_account(commission_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    acc.open_position("BTC/USDT", "crypto", "LONG", 1.0, 100.0)
    equity = acc.get_equity({"BTC/USDT": 120.0})
    assert equity == pytest.approx(10020.0)


def test_unrealized_pnl_computation():
    acc = make_account(commission_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    acc.open_position("BTC/USDT", "crypto", "LONG", 2.0, 100.0)
    upnl = acc.get_unrealized_pnl({"BTC/USDT": 105.0})
    assert upnl == pytest.approx(10.0)


def test_stop_loss_and_take_profit_trigger_detection():
    acc = make_account(commission_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    pos = acc.open_position("EUR/USD", "forex", "LONG", 300, 1.10, stop_loss=1.08, take_profit=1.14)
    # Stop touched
    triggers = acc.check_stops({"EUR/USD": 1.07})
    assert triggers and triggers[0][2] == "stop_loss"
    # Target touched
    triggers = acc.check_stops({"EUR/USD": 1.15})
    assert triggers and triggers[0][2] == "take_profit"


def test_reset_account():
    acc = make_account()
    acc.open_position("BTC/USDT", "crypto", "LONG", 0.1, 100.0)
    acc.reset_account()
    assert acc.balance == 10000.0
    assert acc.get_open_positions() == []