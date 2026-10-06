"""Base class and shared helpers for market-data adapters.

All adapters return a pandas DataFrame with a DatetimeIndex (UTC when the
source provides timestamps) and the columns:
    open, high, low, close, volume
Adapters must never fabricate candles when a provider fails.
"""

from abc import ABC, abstractmethod
from typing import List

import pandas as pd

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


class MarketDataError(Exception):
    """Raised when a data provider cannot return usable data."""


class MarketDataAdapter(ABC):
    """Interface implemented by every market-data source."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Return a normalized OHLCV DataFrame or raise MarketDataError."""

    # -- shared helpers -----------------------------------------------------
    @staticmethod
    def normalize(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names, index, ordering, and remove duplicates.

        Raises MarketDataError if the frame is empty or malformed.
        """
        if df is None or len(df) == 0:
            raise MarketDataError("Provider returned no data")

        df = df.copy()
        # Lower-case column names.
        df.columns = [str(c).lower() for c in df.columns]

        # Map common alternative names.
        rename = {
            "date": "timestamp",
            "datetime": "timestamp",
            "time": "timestamp",
            "vol": "volume",
            "adj close": "close",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise MarketDataError(f"Missing required columns: {missing}")

        # If timestamp is a column, make it the index.
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            df = df.dropna(subset=["timestamp"]).set_index("timestamp")
        else:
            df.index = pd.to_datetime(df.index, utc=True, errors="coerce")

        df = df[REQUIRED_COLUMNS].apply(pd.to_numeric, errors="coerce")

        # Drop rows with no close price.
        df = df.dropna(subset=["close"])

        # Remove duplicate timestamps, keeping the last occurrence.
        df = df[~df.index.duplicated(keep="last")]

        # Sort chronologically so indicators are computed on ordered data.
        df = df.sort_index()

        if len(df) == 0:
            raise MarketDataError("No usable rows after normalization")

        return df

    @staticmethod
    def detect_anomalies(df: pd.DataFrame) -> List[str]:
        """Return a list of human-readable data-quality warnings."""
        warnings: List[str] = []
        if df is None or len(df) == 0:
            warnings.append("Dataset is empty")
            return warnings

        if df.index.has_duplicates:
            warnings.append("Dataset contains duplicate timestamps")
        if not df.index.is_monotonic_increasing:
            warnings.append("Dataset is not sorted by time")
        if df["close"].isna().any():
            warnings.append("Dataset contains missing close prices")
        if (df[["open", "high", "low", "close"]] <= 0).any().any():
            warnings.append("Dataset contains non-positive prices")
        return warnings