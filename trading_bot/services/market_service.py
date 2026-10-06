"""Market data service.

Coordinates the crypto, forex, and synthetic adapters and always tells the
caller *where* the data came from so real and synthetic data can never be
confused in the UI.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from ..logger import setup_logger
from ..market_data.base import MarketDataError
from ..market_data.crypto import CryptoDataProvider
from ..market_data.forex import ForexDataProvider
from ..market_data.synthetic import SyntheticDataProvider

logger = setup_logger(__name__)

CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
FOREX_SYMBOLS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]


@dataclass
class MarketDataResult:
    """A container so the UI always knows the provenance of the data."""

    df: Optional[pd.DataFrame]
    source: str
    is_synthetic: bool
    symbol: str
    market: str
    timeframe: str
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.df is not None and len(self.df) > 0

    @property
    def last_price(self) -> Optional[float]:
        if self.ok:
            return float(self.df["close"].iloc[-1])
        return None

    @property
    def last_time(self):
        if self.ok:
            return self.df.index[-1]
        return None


class MarketService:
    def __init__(self):
        self.crypto = CryptoDataProvider()
        self.forex = ForexDataProvider()
        self.synthetic = SyntheticDataProvider()

    def symbols_for(self, market: str) -> List[str]:
        if market == "crypto":
            return CRYPTO_SYMBOLS
        if market == "forex":
            return FOREX_SYMBOLS
        return CRYPTO_SYMBOLS

    def get_data(
        self,
        market: str = "crypto",
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 500,
        allow_synthetic_fallback: bool = True,
        force_synthetic: bool = False,
    ) -> MarketDataResult:
        """Retrieve OHLCV data and report its source.

        If the real provider fails and ``allow_synthetic_fallback`` is True,
        transparently fall back to clearly-labelled synthetic data.
        """
        if force_synthetic:
            try:
                df = self.synthetic.get_ohlcv(symbol, timeframe, limit)
                return MarketDataResult(
                    df=df,
                    source="synthetic",
                    is_synthetic=True,
                    symbol=symbol,
                    market=market,
                    timeframe=timeframe,
                    warnings=["SYNTHETIC DATA - artificial, not real market prices."],
                )
            except MarketDataError as exc:
                return MarketDataResult(None, "synthetic", True, symbol, market, timeframe, error=str(exc))

        provider = self.crypto if market == "crypto" else self.forex
        try:
            df = provider.get_ohlcv(symbol, timeframe, limit)
            return MarketDataResult(
                df=df,
                source=provider.name,
                is_synthetic=False,
                symbol=symbol,
                market=market,
                timeframe=timeframe,
                warnings=provider.detect_anomalies(df),
            )
        except Exception as exc:
            logger.warning("Provider %s failed for %s: %s", provider.name, symbol, exc)
            error_msg = str(exc)

        if allow_synthetic_fallback:
            try:
                df = self.synthetic.get_ohlcv(symbol, timeframe, limit)
                return MarketDataResult(
                    df=df,
                    source="synthetic",
                    is_synthetic=True,
                    symbol=symbol,
                    market=market,
                    timeframe=timeframe,
                    warnings=[
                        f"Real data unavailable ({error_msg}).",
                        "SYNTHETIC DATA - artificial, not real market prices.",
                    ],
                    error=error_msg,
                )
            except MarketDataError as exc:
                error_msg = f"{error_msg}; synthetic fallback failed: {exc}"

        return MarketDataResult(
            None, provider.name, False, symbol, market, timeframe, error=error_msg
        )