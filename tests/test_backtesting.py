import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.backtesting.performance import PerformanceMetrics, max_drawdown
from trading_bot.simulation.risk_manager import RiskConfig
from trading_bot.strategies.ema_rsi_strategy import EMARsiStrategy


def make_df(closes):
    closes = list(closes)
    n = len(closes)
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [1000.0] * n,
        },
        index=pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC"),
    )


def test_insufficient_data_returns_error():
    df = make_df(np.linspace(100, 110, 10))
    engine = BacktestEngine()
    result = engine.run(df, EMARsiStrategy())
    assert result["ok"] is False
    assert result["trades"] == []


def test_backtest_runs_and_has_metrics():
    df = make_df(np.linspace(100, 200, 200) + np.sin(np.arange(200)) * 5)
    engine = BacktestEngine()
    result = engine.run(df, EMARsiStrategy())
    assert result["ok"] is True
    assert "metrics" in result
    assert result["metrics"]["initial_balance"] == pytest.approx(10000.0)
    assert isinstance(result["equity_curve"], list)


def test_no_lookahead_future_change_does_not_alter_earlier_equity():
    base = make_df(np.linspace(100, 160, 120) + np.sin(np.arange(120)) * 4)
    engine = BacktestEngine()
    result_a = engine.run(base, EMARsiStrategy())

    modified = base.copy()
    modified.iloc[-1, modified.columns.get_loc("close")] = 9999.0
    result_b = engine.run(modified, EMARsiStrategy())

    # Everything before the final bar must be identical.
    n = min(len(result_a["equity_curve"]), len(result_b["equity_curve"]))
    if n > 1:
        assert result_a["equity_curve"][: n - 1] == result_b["equity_curve"][: n - 1]


def test_costs_are_applied():
    df = make_df(np.linspace(100, 200, 200) + np.sin(np.arange(200)) * 5)
    free = BacktestEngine(commission_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    costly = BacktestEngine(commission_pct=0.005, slippage_pct=0.005, spread_pct=0.005)
    r_free = free.run(df, EMARsiStrategy())
    r_cost = costly.run(df, EMARsiStrategy())
    # With costs the final equity should not be better than without.
    if r_free["ok"] and r_cost["ok"]:
        assert r_cost["metrics"]["final_equity"] <= r_free["metrics"]["final_equity"]


def test_max_drawdown_calculation():
    equity = pd.Series([100, 120, 90, 130, 80])
    dd = max_drawdown(equity)
    # Peak 130 -> trough 80 => -38.46%
    assert dd == pytest.approx(-38.4615, abs=0.01)


def test_performance_empty_trades():
    metrics = PerformanceMetrics().calculate([], [10000], 10000)
    assert metrics["total_trades"] == 0
    assert metrics["win_rate"] == 0
    assert metrics["net_profit"] == 0


def test_performance_win_rate_and_profit_factor():
    trades = [
        {"status": "CLOSED", "realized_pnl": 100, "duration": 60},
        {"status": "CLOSED", "realized_pnl": -50, "duration": 120},
        {"status": "CLOSED", "realized_pnl": 100, "duration": 30},
    ]
    metrics = PerformanceMetrics().calculate(trades, [10000, 10150], 10000)
    assert metrics["total_trades"] == 3
    assert metrics["win_rate"] == pytest.approx(66.666, abs=0.01)
    assert metrics["profit_factor"] == pytest.approx(4.0)
    assert metrics["net_profit"] == pytest.approx(150.0)


def test_stop_loss_prevents_large_loss():
    # A descending market should trigger the stop and cap the loss.
    df = make_df(np.linspace(200, 100, 200))
    engine = BacktestEngine(risk_config=RiskConfig(stop_loss_pct=0.02, take_profit_pct=0.04))
    result = engine.run(df, EMARsiStrategy())
    assert result["ok"]
    assert result["metrics"]["net_profit"] > -3000  # bounded, not catastrophic