"""Cryptocurrency market data via CCXT public endpoints.

Only PUBLIC market data (OHLCV) is requested. No API keys are used and no
private/authenticated endpoints are ever called.

Multiple exchanges are tried in order. Kraken is preferred because it is
generally reachable from US-hosted deployments (e.g. Streamlit Community
Cloud), where Binance returns HTTP 451 ("restricted location").
"""

from typing import Dict, List, Optional, Tuple

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

# Exchanges tried in order. Kraken is first because it is reachable from
# US-hosted servers; Binance is kept last because it is geo-restricted there.
_DEFAULT_EXCHANGES = ["kraken", "bybit", "okx", "binance"]


class CryptoDataProvider(MarketDataAdapter):
    """Fetch public OHLCV candles for crypto pairs using CCXT.

    Tries each configured exchange until one returns data, and remembers the
    working exchange for subsequent calls.
    """

    def __init__(self, exchange_id: Optional[str] = None, exchange=None, exchanges=None):
        self._exchanges: List[Tuple[str, object]] = []
        self._preferred_id: Optional[str] = None

        if exchange is not None:
            # An injected/mock exchange (used by tests).
            self._exchanges.append((exchange_id or "custom", exchange))
        else:
            if exchanges is not None:
                ids = list(exchanges)
            elif exchange_id is not None:
                ids = [exchange_id]
            else:
                ids = list(_DEFAULT_EXCHANGES)
            try:
                import ccxt
            except Exception as exc:  # pragma: no cover - depends on env
                logger.warning("ccxt is not importable: %s", exc)
                ccxt = None
            if ccxt is not None:
                for eid in ids:
                    try:
                        inst = getattr(ccxt, eid)(
                            {"enableRateLimit": True, "timeout": 15000}
                        )
                        self._exchanges.append((eid, inst))
                    except Exception as exc:  # pragma: no cover - env dependent
                        logger.warning("Could not initialize CCXT exchange %s: %s", eid, exc)

    @property
    def name(self) -> str:
        if self._preferred_id:
            return f"ccxt-{self._preferred_id}"
        if self._exchanges:
            return f"ccxt-{self._exchanges[0][0]}"
        return "ccxt-unavailable"

    def supports_timeframe(self, timeframe: str) -> bool:
        return timeframe in _TIMEFRAME_MAP

    def _ordered(self) -> List[Tuple[str, object]]:
        """Return exchanges with the last-known-good one first."""
        if not self._preferred_id:
            return self._exchanges
        preferred = [e for e in self._exchanges if e[0] == self._preferred_id]
        rest = [e for e in self._exchanges if e[0] != self._preferred_id]
        return preferred + rest

    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        if not self._exchanges:
            raise MarketDataError("No crypto exchange is available (offline or ccxt missing)")
        if timeframe not in _TIMEFRAME_MAP:
            raise MarketDataError(f"Unsupported timeframe for crypto: {timeframe}")

        errors: List[str] = []
        for eid, exchange in self._ordered():
            try:
                exchange.load_markets()
                if symbol not in exchange.markets:
                    errors.append(f"{eid}: unknown symbol {symbol}")
                    continue
                raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                if not raw:
                    errors.append(f"{eid}: no candles returned")
                    continue
                self._preferred_id = eid
                df = pd.DataFrame(
                    raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                return self.normalize(df.set_index("timestamp"))
            except Exception as exc:  # network, geo-block, rate-limit, etc.
                msg = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
                errors.append(f"{eid}: {msg}")
                logger.warning("Exchange %s failed for %s: %s", eid, symbol, msg)

        raise MarketDataError(
            f"Failed to fetch crypto data for {symbol} from any exchange "
            f"({'; '.join(errors)})"
        )

    def market_tickers(self) -> Dict[str, float]:
        """Return last prices for supported symbols (best effort)."""
        result: Dict[str, float] = {}
        for eid, exchange in self._ordered():
            try:
                tickers = exchange.fetch_tickers()
                for sym in ("BTC/USDT", "ETH/USDT", "SOL/USDT"):
                    if sym in tickers and tickers[sym].get("last") is not None:
                        result[sym] = float(tickers[sym]["last"])
                if result:
                    self._preferred_id = eid
                    return result
            except Exception:  # pragma: no cover - network dependent
                continue
        return result