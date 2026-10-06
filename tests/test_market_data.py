import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from trading_bot.market_data.base import MarketDataAdapter, MarketDataError
from trading_bot.market_data.synthetic import SyntheticDataProvider
from trading_bot.services.market_service import MarketService


def test_synthetic_is_labeled_and_reproducible():
    provider = SyntheticDataProvider(seed=7)
    assert provider.is_synthetic is True
    assert provider.name == "synthetic"
    a = provider.get_ohlcv("BTC/USDT", "1h", 100)
    b = provider.get_ohlcv("BTC/USDT", "1h", 100)
    # Reproducible for the same seed.
    pd.testing.assert_frame_equal(a, b)


def test_synthetic_ohlc_consistency():
    df = SyntheticDataProvider().get_ohlcv("EUR/USD", "1h", 200)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df["close"]).all()
    assert (df["low"] <= df["close"]).all()
    assert df.index.is_monotonic_increasing


def test_synthetic_invalid_timeframe():
    with pytest.raises(MarketDataError):
        SyntheticDataProvider().get_ohlcv("BTC/USDT", "3h", 100)


def test_normalize_rejects_empty():
    with pytest.raises(MarketDataError):
        MarketDataAdapter.normalize(pd.DataFrame())


def test_normalize_raises_on_missing_columns():
    df = pd.DataFrame({"foo": [1, 2, 3]})
    with pytest.raises(MarketDataError):
        MarketDataAdapter.normalize(df)


def test_normalize_sorts_and_deduplicates():
    idx = pd.to_datetime(
        ["2023-01-01T01:00:00Z", "2023-01-01T00:00:00Z", "2023-01-01T01:00:00Z"]
    )
    df = pd.DataFrame(
        {"open": [1, 2, 3], "high": [1, 2, 3], "low": [1, 2, 3], "close": [1, 2, 3], "volume": [1, 1, 1]},
        index=idx,
    )
    out = MarketDataAdapter.normalize(df)
    assert out.index.is_monotonic_increasing
    assert not out.index.has_duplicates


def test_market_service_force_synthetic_flags_source():
    service = MarketService()
    result = service.get_data("crypto", "BTC/USDT", "1h", 100, force_synthetic=True)
    assert result.ok
    assert result.is_synthetic is True
    assert result.source == "synthetic"
    assert any("SYNTHETIC" in w.upper() for w in result.warnings)


def test_market_service_offline_fallback_is_labeled():
    service = MarketService()
    # An invalid forex timeframe forces a provider failure; fallback must be labelled.
    result = service.get_data("forex", "EUR/USD", "4h", 100, allow_synthetic_fallback=True)
    if result.ok and result.source == "synthetic":
        assert result.is_synthetic is True
        assert any("SYNTHETIC" in w.upper() for w in result.warnings)