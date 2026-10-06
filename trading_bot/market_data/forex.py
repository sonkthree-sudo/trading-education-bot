"""Forex market data via yfinance as an *educational* historical source.

IMPORTANT LIMITATIONS (shown to the user in the UI):
  * Yahoo Finance is NOT a broker and is not a guaranteed real-time feed.
  * Intraday forex history is limited and may contain gaps, delays, or
    restricted intervals.
  * Volume is usually 0 for FX and should not be treated as meaningful.
This adapter only retrieves historical data for learning. It never trades.
"""

from typing import Dict

import pandas as pd

from .base import MarketDataAdapter, MarketDataError
from ..logger import setup_logger

logger = setup_logger(__name__)


class ForexDataProvider(MarketDataAdapter):
    """Fetch historical forex candles from yfinance (educational fallback)."""

    # Map friendly pairs to Yahoo tickers.
    _PAIR_MAP = {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CHF": "USDCHF=X",
        "USD/CAD": "USDCAD=X",
        "NZD/USD": "NZDUSD=X",
    }

    # yfinance intraday intervals (period strings chosen to be reliable).
    _INTERVAL_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "60m",
        "1d": "1d",
    }

    _PERIOD_FOR_INTERVAL = {
        "1m": "7d",
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "1h": "730d",
        "1d": "5y",
    }

    @property
    def name(self) -> str:
        return "yfinance-forex"

    def supports_timeframe(self, timeframe: str) -> bool:
        return timeframe in self._INTERVAL_MAP

    @staticmethod
    def supported_pairs():
        return list(ForexDataProvider._PAIR_MAP.keys())

    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        ticker = self._PAIR_MAP.get(symbol)
        if ticker is None:
            # Allow raw ticker strings too.
            ticker = symbol if symbol.endswith("=X") else symbol.replace("/", "") + "=X"

        if timeframe not in self._INTERVAL_MAP:
            raise MarketDataError(f"Unsupported timeframe for forex: {timeframe}")

        try:
            import yfinance as yf
        except Exception as exc:  # pragma: no cover
            raise MarketDataError(f"yfinance is not installed: {exc}") from exc

        try:
            interval = self._INTERVAL_MAP[timeframe]
            period = self._PERIOD_FOR_INTERVAL[timeframe]
            raw = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=False,
            )
        except Exception as exc:
            raise MarketDataError(f"Failed to fetch forex data for {symbol}: {exc}") from exc

        if raw is None or raw.empty:
            raise MarketDataError(
                f"Yahoo Finance returned no data for {symbol} ({timeframe}). "
                "Forex availability is limited and may be delayed."
            )

        # yfinance may return a MultiIndex when downloading a single ticker.
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        raw = raw.reset_index()
        return self.normalize(raw).tail(limit)

    def last_price(self, symbol: str) -> Dict[str, float]:
        df = self.get_ohlcv(symbol, "1h", limit=1)
        return {symbol: float(df["close"].iloc[-1])} if len(df) else {}