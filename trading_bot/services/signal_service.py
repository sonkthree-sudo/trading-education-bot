"""Signal and analysis service.

Wraps indicator calculation, candlestick detection, and strategy evaluation
so the dashboard stays thin. Everything here is causal (no look-ahead).
"""

from typing import Any, Dict, List

import pandas as pd

from ..indicators.candlestick_patterns import describe_patterns
from ..indicators.technical_indicators import add_all_indicators
from ..strategies.base_strategy import Signal
from ..strategies.strategy_manager import get_strategy


class SignalService:
    def compute_indicators(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        if df is None or len(df) == 0:
            return df
        return add_all_indicators(df, **kwargs)

    def generate_signal(self, df: pd.DataFrame, strategy_name: str = "EMA_RSI", **params) -> Signal:
        if df is None or len(df) == 0:
            return Signal(action="WAIT", reason="No data loaded")
        strategy = get_strategy(strategy_name, **params)
        return strategy.generate_signal(df)

    def patterns(self, df: pd.DataFrame, tail: int = 20) -> List[Dict[str, Any]]:
        if df is None or len(df) == 0:
            return []
        events = describe_patterns(df)
        return events[-tail:]

    @staticmethod
    def compare_signals(df: pd.DataFrame, configs: List[Dict[str, Any]], strategy_name: str = "EMA_RSI"):
        """Evaluate several parameter sets on the same latest candle."""
        rows = []
        for cfg in configs:
            strategy = get_strategy(strategy_name, **cfg)
            signal = strategy.generate_signal(df)
            rows.append({"config": cfg, "signal": signal.as_dict()})
        return rows