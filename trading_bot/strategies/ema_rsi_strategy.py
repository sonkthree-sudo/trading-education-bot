"""Explainable EMA + RSI strategy (long and short).

Long setup : EMA9 > EMA21, RSI in a configurable momentum band, and optional
             trend confirmation (price above EMA50).
Short setup: EMA9 < EMA21, RSI in a configurable momentum band, and optional
             trend confirmation (price below EMA50).
Signals are evaluated only on candle close.
"""

from typing import Any, Dict

import pandas as pd

from .base_strategy import BaseStrategy, Signal
from ..indicators.technical_indicators import add_all_indicators


class EMARsiStrategy(BaseStrategy):
    name = "EMA_RSI"
    display_name = "EMA + RSI crossover"
    description = (
        "Trend-following strategy. Buys when the fast EMA is above the slow EMA "
        "and RSI confirms momentum, and sells when the fast EMA is below the "
        "slow EMA. An optional EMA50 filter trades only with the wider trend."
    )

    def __init__(
        self,
        ema_fast: int = 9,
        ema_slow: int = 21,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        use_trend_filter: bool = False,
        ema_trend: int = 50,
    ):
        super().__init__(
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi_period=rsi_period,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            use_trend_filter=use_trend_filter,
            ema_trend=ema_trend,
        )
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.use_trend_filter = use_trend_filter
        self.ema_trend = ema_trend

    @property
    def min_candles(self) -> int:
        base = max(self.ema_slow, self.rsi_period + 1, self.ema_trend if self.use_trend_filter else 0)
        return base + 5

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        return add_all_indicators(
            df,
            ema_fast=self.ema_fast,
            ema_slow=self.ema_slow,
            ema_trend=self.ema_trend,
            rsi_period=self.rsi_period,
        )

    def evaluate(self, df: pd.DataFrame, index: int) -> Signal:
        row = df.iloc[index]
        fast = row[f"ema{self.ema_fast}"] if f"ema{self.ema_fast}" in df.columns else row["ema9"]
        slow = row[f"ema{self.ema_slow}"] if f"ema{self.ema_slow}" in df.columns else row["ema21"]
        rsi_val = row[f"rsi{self.rsi_period}"] if f"rsi{self.rsi_period}" in df.columns else row["rsi14"]
        trend = row[f"ema{self.ema_trend}"] if f"ema{self.ema_trend}" in df.columns else row.get("ema50")

        if pd.isna(fast) or pd.isna(slow) or pd.isna(rsi_val):
            return Signal(action="WAIT", reason="Indicators not yet available", index=index)

        indicators = {
            "ema_fast": round(float(fast), 6),
            "ema_slow": round(float(slow), 6),
            "rsi": round(float(rsi_val), 2),
        }
        if trend is not None and not pd.isna(trend):
            indicators["ema_trend"] = round(float(trend), 6)

        ts = df.index[index]
        price = float(row["close"])

        uptrend = fast > slow
        downtrend = fast < slow
        in_band = self.rsi_oversold < rsi_val < self.rsi_overbought

        if self.use_trend_filter and trend is not None and not pd.isna(trend):
            uptrend = uptrend and price > trend
            downtrend = downtrend and price < trend

        if uptrend and in_band:
            return Signal(
                action="BUY",
                reason=(
                    f"EMA{self.ema_fast} above EMA{self.ema_slow} "
                    f"and RSI {rsi_val:.1f} inside {self.rsi_oversold:.0f}-{self.rsi_overbought:.0f}"
                ),
                index=index,
                price=price,
                timestamp=ts,
                indicators=indicators,
            )
        if downtrend and in_band:
            return Signal(
                action="SELL",
                reason=(
                    f"EMA{self.ema_fast} below EMA{self.ema_slow} "
                    f"and RSI {rsi_val:.1f} inside {self.rsi_oversold:.0f}-{self.rsi_overbought:.0f}"
                ),
                index=index,
                price=price,
                timestamp=ts,
                indicators=indicators,
            )

        if not in_band:
            reason = f"RSI {rsi_val:.1f} outside momentum band"
        else:
            reason = "No EMA crossover / trend alignment"
        return Signal(action="WAIT", reason=reason, index=index, price=price, timestamp=ts, indicators=indicators)

    def config(self) -> Dict[str, Any]:
        return {
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
            "rsi_period": self.rsi_period,
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
            "use_trend_filter": self.use_trend_filter,
            "ema_trend": self.ema_trend,
        }