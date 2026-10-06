"""Risk management reference.

This page is enforced in code by ``trading_bot/simulation/risk_manager.py`` and
persisted by the storage layer, so rules survive app restarts.
"""

# RISK_MANAGEMENT

## Default (conservative) settings
| Setting | Default | Meaning |
|---|---|---|
| Starting balance | $10,000 | Virtual cash |
| Max position notional | 5% of equity | Largest single position |
| Max risk per trade | 1% of equity | Estimated loss at the stop |
| Daily loss limit | 3% of day-start equity | Pauses new trades |
| Max open positions | 1 | Initially one per symbol |
| Max total exposure | 20% of equity | All positions combined |
| Max consecutive losses | 5 | Triggers a pause |
| Stop-loss | 2% | Default stop distance |
| Take-profit | 4% | Default target (2:1 reward:risk) |

## Key distinctions
- **Notional value** = quantity x price. It is the size of the position.
- **Risk at the stop** = quantity x |entry - stop|. It is the money you lose if
  the stop fills. These are *different* numbers. Risk-based sizing uses the
  second one.

## What risk controls do
1. **Position sizing** - quantity is chosen so the loss at the stop is <= 1% of
   equity, and the notional is <= 5% of equity.
2. **Daily loss limit** - if the day's loss (realized + unrealized) reaches 3%
   of the day-start equity, new trades are blocked.
3. **Consecutive losses** - after 5 losing trades in a row, new trades pause.
4. **Exposure cap** - total open notional may not exceed 20% of equity.
5. **One position per symbol** - prevents accidental doubling up.
6. **Emergency pause** - a manual switch that blocks all new trades.

## Persistence and audit
- Daily counters, consecutive losses, and the emergency flag are saved in
  SQLite and restored on startup.
- Refreshing the page or restarting the app does **not** clear a lockout.
- Resets are explicit and recorded in the event log (audit trail).

## Honest limitations
- A stop-loss is **not** a guarantee. Gaps and slippage can fill your order at
  a worse price than the stop, producing a larger loss than planned.
- Intraday, with only OHLC candles, we cannot know whether the stop or target
  was hit first. The backtester assumes the stop first (conservative).
- Daily loss uses the day-start equity as the reference, matching common
  professional practice, so a large unrealized swing can trigger a pause.
- Sizing assumes the stop will be respected; correlated positions (for example
  several crypto pairs) tend to lose together, which the single-position limit
  only partly addresses.

## User-controlled reset procedure
1. Open **Risk Management**.
2. Review the current status and the audit log.
3. Press **Reset risk lockouts (audited)** to resume trading, or
   **Reset paper account** in Settings to start the whole simulation over
  (requires confirmation).