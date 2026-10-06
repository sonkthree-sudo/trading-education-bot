"""Cryptocurrency market data via CCXT public endpoints.

Only PUBLIC market data (OHLCV) is requested. No API keys are used and no
private/authenticated endpoints are ever called.
"""

from typing import Dict

import pandas as pd

from .base import MarketDataAdapter, MarketDataError
from ..logger import setup_logger

logger = setup_logger(__name__)

# Timeframes shared by most CCXT exchanges.
_TIMEFRAME_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


class CryptoDataProvider(MarketDataAdapter):
    """Fetch public OHLCV candles for crypto pairs using CCXT/Binance."""

    def __init__(self, exchange_id: str = "binance", exchange=None):
        self._exchange_id = exchange_id
        self._exchange = exchange
        if self._exchange is None:
            try:
                import ccxt

                self._exchange = getattr(ccxt, exchange_id)({
                    "enableRateLimit": True,
                    "timeout": 15000,
                })
            except Exception as exc:  # pragma: no cover - depends on env
                logger.warning("Could not initialize CCXT exchange: %s", exc)
                self._exchange = None

    @property
    def name(self) -> str:
        return f"ccxt-{self._exchange_id}"

    def supports_timeframe(self, timeframe: str) -> bool:
        return timeframe in _TIMEFRAME_MAP

    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        if self._exchange is None:
            raise MarketDataError("Crypto exchange is not available (offline or ccxt missing)")

        if timeframe not in _TIMEFRAME_MAP:
            raise MarketDataError(f"Unsupported timeframe for crypto: {timeframe}")

        try:
            self._exchange.load_markets()
            if symbol not in self._exchange.markets:
                raise MarketDataError(f"Unknown symbol on {self._exchange_id}: {symbol}")
            raw = self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except MarketDataError:
            raise
        except Exception as exc:  # network, rate-limit, etc.
            raise MarketDataError(f"Failed to fetch crypto data for {symbol}: {exc}") from exc

        if not raw:
            raise MarketDataError(f"Exchange returned no candles for {symbol}")

        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return self.normalize(df.set_index("timestamp"))

    def market_tickers(self) -> Dict[str, float]:
        """Return last prices for supported symbols (best effort)."""
        result: Dict[str, float] = {}
        if self._exchange is None:
            return result
        try:
            tickers = self._exchange.fetch_tickers()
            for sym in ("BTC/USDT", "ETH/USDT", "SOL/USDT"):
                if sym in tickers and tickers[sym].get("last") is not None:
                    result[sym] = float(tickers[sym]["last"])
        except Exception:  # pragma: no cover - network dependent
            pass
        return result