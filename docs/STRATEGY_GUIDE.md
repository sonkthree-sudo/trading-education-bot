# Strategy Guide

This document explains the included strategy, how signals are produced, and
why. Nothing here is financial advice and no strategy guarantees profits.

## Included strategy: EMA + RSI crossover (`EMA_RSI`)

### Idea
Markets trend. A fast exponential moving average (EMA) turning above a slower
EMA can indicate the start of an up-move; the opposite suggests a downtrend.
RSI is used as a momentum filter so we avoid entering when momentum is already
extreme.

### Rules
Default parameters:

| Parameter        | Default | Meaning                                    |
|------------------|---------|--------------------------------------------|
| `ema_fast`       | 9       | Fast EMA |
| `ema_slow`       | 21      | Slow EMA |
| `rsi_period`     | 14      | RSI look-back                              |
| `rsi_oversold`   | 30      | Lower RSI bound for entries                |
| `rsi_overbought` | 70      | Upper RSI bound for entries                |
| `use_trend_filter` | False | Require price to align with EMA50          |
| `ema_trend`      | 50      | Trend filter EMA                           |

BUY when:
- EMA9 > EMA21, AND
- RSI is inside the 30-70 momentum band
- (optional) price is above EMA50

SELL (short) when:
- EMA9 < EMA21
- RSI is inside the momentum band
- (optional) price is below EMA50

Otherwise the signal is WAIT.

### Why signals are "explainable"
Every signal carries a plain-language reason and a snapshot of the indicator
values that produced it, so you can see exactly *why* the bot chose BUY, SELL,
or WAIT.

### No look-ahead
Signals are computed from a candle's close only. The backtester enters at the
NEXT candle's open. Appending future candles cannot change an earlier signal.

## Backtesting rules
- Entry: next candle's open after a signal.
- Stop-loss and take-profit: fixed percentages from the entry (configurable).
- If one candle touches both stop and target, the STOP is assumed first
  (conservative).
- Commission, spread, and slippage are all applied.
- Position size is risk-based (default 1% of equity risked per trade).

## Comparing configurations
The Strategy Lab lets you change parameters and re-run. Test several settings,
but remember: a configuration that worked historically may fail in the future.
Look at the number of trades too - a strategy with 3 trades proves very little.

## Extending with your own strategy
1. Create a class in `trading_bot/strategies/` subclassing `BaseStrategy`.
2. Implement `prepare(df)` (add indicators) and `evaluate(df, index)` (return a
   `Signal`).
3. Register it in `strategy_manager.py`.

Keep `evaluate` causal - never read rows after `index`.