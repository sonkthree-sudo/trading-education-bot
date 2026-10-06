import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from trading_bot.indicators import technical_indicators as ti


def test_ema_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = ti.ema(s, 2)
    assert len(result) == len(s)
    assert pd.notna(result.iloc[-1])
    # EMA of an increasing series must be below the last value but above start.
    assert 1.0 < result.iloc[-1] < 5.0


def test_ema_invalid_period():
    with pytest.raises(ValueError):
        ti.ema(pd.Series([1, 2, 3]), 0)


def test_rsi_bounds_and_direction():
    up = pd.Series(np.arange(1, 40, dtype=float))
    rsi_up = ti.rsi(up, 14)
    assert rsi_up.dropna().between(0, 100).all()
    # Relentless up moves should push RSI high.
    assert rsi_up.iloc[-1] > 90

    down = pd.Series(np.arange(40, 1, -1, dtype=float))
    rsi_down = ti.rsi(down, 14)
    assert rsi_down.iloc[-1] < 10


def test_rsi_all_gains_is_100():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], dtype=float)
    rsi = ti.rsi(s, 14)
    assert rsi.iloc[-1] == pytest.approx(100.0)


def test_macd_columns():
    s = pd.Series(np.linspace(10, 20, 60))
    out = ti.macd(s)
    assert list(out.columns) == ["macd", "signal", "hist"]


def test_bollinger_bands_order():
    s = pd.Series(np.random.default_rng(0).normal(100, 2, 100))
    out = ti.bollinger_bands(s, 20)
    valid = out.dropna()
    assert (valid["upper"] >= valid["middle"]).all()
    assert (valid["middle"] >= valid["lower"]).all()


def test_missing_data_handling():
    s = pd.Series([1.0, np.nan, 3.0, 4.0, 5.0])
    result = ti.ema(s.ffill(), 2)
    assert len(result) == len(s)


def test_add_all_indicators_no_lookahead():
    # Changing the final candle must not alter earlier indicator values.
    base = pd.DataFrame(
        {
            "open": np.linspace(100, 120, 80),
            "high": np.linspace(101, 121, 80),
            "low": np.linspace(99, 119, 80),
            "close": np.linspace(100, 120, 80),
            "volume": np.full(80, 1000.0),
        },
        index=pd.date_range("2023-01-01", periods=80, freq="1h", tz="UTC"),
    )
    a = ti.add_all_indicators(base)
    modified = base.copy()
    modified.iloc[-1, modified.columns.get_loc("close")] *= 1.5
    b = ti.add_all_indicators(modified)
    # All but the last row of every indicator must be identical.
    for col in ("ema9", "ema21", "rsi14", "macd", "bb_upper"):
        pd.testing.assert_series_equal(a[col].iloc[:-1], b[col].iloc[:-1])


def test_insufficient_data_is_handled():
    tiny = pd.DataFrame(
        {"open": [1, 2], "high": [2, 3], "low": [0.5, 1], "close": [1.5, 2.5], "volume": [1, 1]},
        index=pd.date_range("2023-01-01", periods=2, freq="1h", tz="UTC"),
    )
    # Must not crash on tiny data, and RSI (which needs a full window) stays NaN.
    out = ti.add_all_indicators(tiny)
    assert len(out) == 2
    assert out["rsi14"].isna().all()
    assert out["bb_upper"].isna().all()