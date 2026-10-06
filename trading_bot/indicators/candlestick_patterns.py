"""Candlestick pattern detection.

Each detector returns a boolean pandas Series aligned to the input index.
Patterns are described in plain language by ``describe_patterns`` so the
learning center can explain *why* a candle matched.
"""

from typing import Dict, List

import pandas as pd


def _body(row) -> float:
    return abs(row["close"] - row["open"])


def _range(row) -> float:
    rng = row["high"] - row["low"]
    return rng if rng > 0 else 1e-10


def detect_engulfing(df: pd.DataFrame) -> pd.Series:
    """Bullish or bearish engulfing: the body engulfs the previous body."""
    result = pd.Series(False, index=df.index)
    if len(df) < 2:
        return result
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        prev_bull = prev["close"] > prev["open"]
        prev_bear = prev["close"] < prev["open"]
        curr_bull = curr["close"] > curr["open"]
        curr_bear = curr["close"] < curr["open"]
        if prev_bear and curr_bull:
            if curr["open"] <= prev["close"] and curr["close"] >= prev["open"]:
                result.iloc[i] = True
        elif prev_bull and curr_bear:
            if curr["open"] >= prev["close"] and curr["close"] <= prev["open"]:
                result.iloc[i] = True
    return result


def detect_hammer(df: pd.DataFrame, body_ratio: float = 0.35, lower_wick_ratio: float = 2.0) -> pd.Series:
    """Hammer / pin bar with a long lower wick and small body."""
    result = pd.Series(False, index=df.index)
    for i in range(len(df)):
        row = df.iloc[i]
        body = _body(row)
        rng = _range(row)
        upper_wick = row["high"] - max(row["open"], row["close"])
        lower_wick = min(row["open"], row["close"]) - row["low"]
        if body / rng <= body_ratio and lower_wick >= body * lower_wick_ratio and upper_wick <= body:
            result.iloc[i] = True
    return result


def detect_shooting_star(df: pd.DataFrame, body_ratio: float = 0.35, upper_wick_ratio: float = 2.0) -> pd.Series:
    """Shooting star: long upper wick and small body near the low."""
    result = pd.Series(False, index=df.index)
    for i in range(len(df)):
        row = df.iloc[i]
        body = _body(row)
        rng = _range(row)
        upper_wick = row["high"] - max(row["open"], row["close"])
        lower_wick = min(row["open"], row["close"]) - row["low"]
        if body / rng <= body_ratio and upper_wick >= body * upper_wick_ratio and lower_wick <= body:
            result.iloc[i] = True
    return result


def detect_doji(df: pd.DataFrame, body_ratio: float = 0.1) -> pd.Series:
    """Doji: open and close are almost equal (indecision)."""
    result = pd.Series(False, index=df.index)
    for i in range(len(df)):
        row = df.iloc[i]
        if _body(row) / _range(row) <= body_ratio:
            result.iloc[i] = True
    return result


PATTERN_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "engulfing": {
        "name": "Engulfing candle",
        "conditions": "The current body completely covers the previous candle's body, and the two candles have opposite colours.",
        "why": "A sharp reversal in control from sellers to buyers (bullish) or buyers to sellers (bearish).",
        "limitations": "Common and easy to fake; stronger near support/resistance and with high volume.",
    },
    "hammer": {
        "name": "Hammer / Pin bar",
        "conditions": "Small body near the top, long lower wick at least twice the body, little or no upper wick.",
        "why": "Sellers pushed price down but buyers rejected the move, often near a swing low.",
        "limitations": "Needs confirmation on the next candle; appearing mid-trend is often noise.",
    },
    "shooting_star": {
        "name": "Shooting star",
        "conditions": "Small body near the bottom, long upper wick at least twice the body, little or no lower wick.",
        "why": "Buyers pushed price up but sellers rejected the move, often near a swing high.",
        "limitations": "Needs confirmation; unreliable in strong uptrends.",
    },
    "doji": {
        "name": "Doji",
        "conditions": "Open and close are almost equal, so the body is tiny relative to the range.",
        "why": "Signals indecision and a possible pause or reversal in trend.",
        "limitations": "Very common and not directional on its own; context is essential.",
    },
}


def describe_patterns(df: pd.DataFrame) -> List[Dict[str, object]]:
    """Return a list of detected pattern events with explanation metadata."""
    detectors = {
        "engulfing": detect_engulfing,
        "hammer": detect_hammer,
        "shooting_star": detect_shooting_star,
        "doji": detect_doji,
    }
    events: List[Dict[str, object]] = []
    for key, detector in detectors.items():
        flags = detector(df)
        for ts in df.index[flags]:
            info = PATTERN_DESCRIPTIONS[key]
            events.append(
                {
                    "pattern": info["name"],
                    "key": key,
                    "timestamp": ts,
                    "conditions": info["conditions"],
                    "why": info["why"],
                    "limitations": info["limitations"],
                    "close": float(df.loc[ts, "close"]),
                }
            )
    events.sort(key=lambda e: e["timestamp"])
    return events