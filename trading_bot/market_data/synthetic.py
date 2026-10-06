"""SYNTHETIC (artificial) market data for offline learning.

This data is FABRICATED. It is NOT historical market evidence and must never
be mistaken for real prices. It exists so a beginner can explore indicators,
signals, paper trading, and backtesting without any internet connection.

The generator is deterministic for a given seed so results are reproducible.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .base import MarketDataAdapter, MarketDataError

# Timeframe -> pandas frequency alias.
_FREQ_MAP = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}

# Rough starting price per known symbol (purely cosmetic).
_START_PRICE = {
    "BTC/USDT": 30000.0,
    "ETH/USDT": 2000.0,
    "SOL/USDT": 30.0,
    "EUR/USD": 1.10,
    "GBP/USD": 1.27,
    "USD/JPY": 150.0,
    "AUD/USD": 0.66,
}


class SyntheticDataProvider(MarketDataAdapter):
    """Reproducible, clearly-labelled artificial OHLCV data."""

    is_synthetic = True

    def __init__(self, seed: int = 42):
        self.seed = seed

    @property
    def name(self) -> str:
        return "synthetic"

    def get_ohlcv(self, symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        if timeframe not in _FREQ_MAP:
            raise MarketDataError(f"Unsupported synthetic timeframe: {timeframe}")

        limit = int(limit)
        if limit <= 0:
            raise MarketDataError("limit must be > 0")

        rng = np.random.default_rng(self.seed)
        start = _START_PRICE.get(symbol, 100.0)
        # Scale volatility so small-price pairs (FX) do not explode.
        vol = max(start * 0.005, 1e-4)

        # Geometric-ish random walk with slight mean reversion and drift.
        steps = rng.normal(loc=0.0, scale=1.0, size=limit)
        prices = [start]
        for i in range(1, limit):
            drift = 0.0002 * start
            change = steps[i] * vol + drift
            new_price = max(prices[-1] + change, start * 0.1)
            prices.append(new_price)
        close = np.array(prices, dtype=float)

        opens = np.concatenate([[close[0]], close[:-1]])
        noise = np.abs(rng.normal(0.0, vol, size=limit))
        highs = np.maximum(opens, close) + noise
        lows = np.minimum(opens, close) - noise
        volumes = rng.integers(1000, 10000, size=limit).astype(float)

        end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        freq = _FREQ_MAP[timeframe]
        index = pd.date_range(end=end, periods=limit, freq=freq, tz="UTC")

        df = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": close,
                "volume": volumes,
            },
            index=index,
        )
        return self.normalize(df)