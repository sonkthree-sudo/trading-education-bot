"""Market-data adapters."""

from .base import MarketDataAdapter, MarketDataError
from .crypto import CryptoDataProvider
from .forex import ForexDataProvider
from .synthetic import SyntheticDataProvider

__all__ = [
    "MarketDataAdapter",
    "MarketDataError",
    "CryptoDataProvider",
    "ForexDataProvider",
    "SyntheticDataProvider",
]