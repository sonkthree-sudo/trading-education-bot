"""Strategy base class and the shared Signal structure."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class Signal:
    """An explainable trading signal produced at a specific candle close."""

    action: str = "WAIT"          # BUY | SELL | WAIT
    reason: str = ""
    index: int = -1
    price: Optional[float] = None
    timestamp: Any = None
    indicators: Dict[str, Any] = field(default_factory=dict)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        ts = self.timestamp
        try:
            ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        except Exception:
            ts = str(ts)
        return {
            "action": self.action,
            "reason": self.reason,
            "index": self.index,
            "price": self.price,
            "timestamp": ts,
            "indicators": self.indicators,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
        }


class BaseStrategy(ABC):
    """Every strategy evaluates the *latest known* candle only.

    Implementations must not read candles after ``index`` to avoid look-ahead
    bias. They must also return WAIT (never a trade) when there is not enough
    data to compute the indicators reliably.
    """

    name = "Base"
    display_name = "Base strategy"
    description = ""

    def __init__(self, **params):
        self.params = dict(params)

    @property
    def min_candles(self) -> int:
        return 50

    @abstractmethod
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return df with indicator columns added (causal)."""

    @abstractmethod
    def evaluate(self, df: pd.DataFrame, index: int) -> Signal:
        """Evaluate a single closed candle at ``index``."""

    def generate_signal(self, df: pd.DataFrame, index: int = -1) -> Signal:
        if df is None or len(df) == 0:
            return Signal(action="WAIT", reason="No data available")
        idx = len(df) - 1 if index < 0 else index
        if idx < 0 or idx >= len(df):
            idx = len(df) - 1
        if len(df) < self.min_candles:
            return Signal(
                action="WAIT",
                reason=f"Not enough history ({len(df)}/{self.min_candles} candles) to compute indicators reliably",
                index=idx,
            )
        data = self.prepare(df)
        return self.evaluate(data, idx)

    def config(self) -> Dict[str, Any]:
        return dict(self.params)