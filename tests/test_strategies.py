import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from trading_bot.indicators.candlestick_patterns import describe_patterns
from trading_bot.strategies.ema_rsi_strategy import EMARsiStrategy


def make_df(closes):
    closes = list(closes)
    n = len(closes)
    return pd.DataFrame(
        {
            "open": [c - 0.2 for c in closes],
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": [1000.0] * n,
        },
        index=pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC"),
    )


def test_signal_waits_with_insufficient_data():
    strategy = EMARsiStrategy()
    df = make_df(np.linspace(100, 105, 10))
    signal = strategy.generate_signal(df)
    assert signal.action == "WAIT"
    assert "Not enough history" in signal.reason


def test_signal_generated_on_uptrend():
    strategy = EMARsiStrategy()
    df = make_df(np.linspace(100, 160, 80))
    signal = strategy.generate_signal(df)
    # A steady uptrend with mid RSI should produce a BUY or a WAIT with a reason,
    # never a crash and never a SELL.
    assert signal.action in ("BUY", "WAIT")
    assert signal.action != "SELL"
    assert signal.reason


def test_trend_filter_blocks_against_trend():
    df = make_df(np.linspace(100, 160, 80))
    strategy = EMARsiStrategy(use_trend_filter=True)
    signal = strategy.generate_signal(df)
    assert signal.action in ("BUY", "WAIT")


def test_signal_uses_only_past_data():
    strategy = EMARsiStrategy()
    df = make_df(np.linspace(100, 160, 80))
    # Signal at index 60 must not change if we append future candles.
    base_signal = strategy.generate_signal(df, index=60)
    extended = make_df(list(np.linspace(100, 160, 80)) + [500, 600, 700])
    extended_signal = strategy.generate_signal(extended, index=60)
    assert base_signal.action == extended_signal.action
    assert base_signal.indicators == extended_signal.indicators


def test_describe_patterns_engulfing():
    df = pd.DataFrame(
        {
            "open": [10.0, 7.5],
            "high": [10.2, 12.2],
            "low": [7.8, 7.4],
            "close": [8.0, 12.0],
            "volume": [1000.0, 1500.0],
        },
        index=pd.date_range("2023-01-01", periods=2, freq="1h", tz="UTC"),
    )
    events = describe_patterns(df)
    names = {e["key"] for e in events}
    assert "engulfing" in names
    for event in events:
        assert set(["pattern", "conditions", "why", "limitations"]).issubset(event.keys())