"""Technical indicators implemented with pandas.

All functions accept a pandas Series and return a Series (or DataFrame) with
the same index. They only use information available up to each point in time
(rolling / exponential windows), so there is no look-ahead bias.
"""

import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    if period <= 0:
        raise ValueError("SMA period must be > 0")
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average (adjust=False for recursive EMA)."""
    if period <= 0:
        raise ValueError("EMA period must be > 0")
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index using Wilder's smoothing."""
    if period <= 0:
        raise ValueError("RSI period must be > 0")
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    out = 100.0 - (100.0 / (1.0 + rs))
    # When avg_loss is 0 and avg_gain > 0, RSI is 100.
    out = out.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    return out


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """Moving Average Convergence Divergence."""
    if min(fast, slow, signal) <= 0:
        raise ValueError("MACD periods must be > 0")
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    """Bollinger Bands."""
    if period <= 0:
        raise ValueError("Bollinger period must be > 0")
    middle = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std()
    return pd.DataFrame(
        {
            "upper": middle + std * std_dev,
            "middle": middle,
            "lower": middle - std * std_dev,
        }
    )


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing)."""
    if period <= 0:
        raise ValueError("ATR period must be > 0")
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def add_all_indicators(
    df: pd.DataFrame,
    ema_fast: int = 9,
    ema_slow: int = 21,
    ema_trend: int = 50,
    rsi_period: int = 14,
    bb_period: int = 20,
) -> pd.DataFrame:
    """Return a copy of ``df`` with a standard set of indicators added."""
    data = df.copy()
    data["ema9"] = ema(data["close"], ema_fast)
    data["ema21"] = ema(data["close"], ema_slow)
    data["ema50"] = ema(data["close"], ema_trend)
    data["rsi14"] = rsi(data["close"], rsi_period)
    macd_df = macd(data["close"])
    data["macd"] = macd_df["macd"]
    data["macd_signal"] = macd_df["signal"]
    data["macd_hist"] = macd_df["hist"]
    bb = bollinger_bands(data["close"], bb_period)
    data["bb_upper"] = bb["upper"]
    data["bb_middle"] = bb["middle"]
    data["bb_lower"] = bb["lower"]
    if {"high", "low"}.issubset(data.columns):
        data["atr14"] = atr(data["high"], data["low"], data["close"])
    return data