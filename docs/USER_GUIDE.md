# User Guide

Welcome! This guide walks a complete beginner through using the Trading
Education Bot. Everything here is **simulated** — you cannot lose real money.

## 1. Starting the app

```powershell
cd D:\Projects\trading-education-bot
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

A browser tab opens. If it does not, copy the `http://localhost:8501` link
from the terminal.

## 2. The sidebar

The sidebar is your control panel:

| Control | What it does |
|---------|--------------|
| Navigation | Switch between dashboard pages |
| Market | `crypto` or `forex` |
| Symbol | The pair to study |
| Timeframe | Candle size (1m … 1d) |
| Candles | How much history to load |
| Force synthetic data | Offline, artificial data for practice |

For forex you will see a note that Yahoo Finance data is historical and may be
delayed. If the internet is unavailable the app automatically switches to
**clearly-labelled synthetic data**.

## 3. Reading data provenance

At the top of data pages a banner tells you exactly where data came from:

- **Green** – real/historical data from a named provider.
- **Amber** – **SYNTHETIC** data (artificial). Practice only.

Always trust the banner, never assume prices are live.

## 4. Overview page

A snapshot of your paper account:

- Cash balance, equity, realized and unrealized P&L.
- Open positions, closed trades, win rate.
- Daily loss and remaining daily allowance.
- Risk status (ACTIVE or PAUSED).
- The latest explainable signal.

## 5. ExplorING a market

Open **Market Explorer** to see the most recent candles for the selected pair.
Open **Chart** for:

- Candlesticks with EMA 9/21/50.
- RSI (14) in its own panel (dashed 30/70 lines).
- MACD in its own panel.
- Optional Bollinger Bands and pattern markers.

Indicators are blank until enough candles exist — that is intentional.

## 6. Signals (Signal Center)

The **Signal Center** evaluates the last closed candle and prints:

- **BUY** – fast EMA above slow EMA with RSI in range.
- **SELL** – fast EMA below slow EMA with RSI in range.
- **WAIT** – conditions not met (the reason is always shown).

An entry signal is **not** an instruction to trade. Signals appear only after a
candle closes and never guarantee profit.

## 7. Placing a paper trade

1. Go to **Paper Trading** and make sure real or synthetic data is loaded.
2. Choose side (LONG/SHORT).
3. Choose a stop-loss and take-profit percentage.
4. Pick a sizing basis:
   - **Risk-based** sizes the trade so a stop-out loses ~1% of equity.
   - **Fixed notional** uses 5% of equity.
5. Click **Open paper position**.
6. Close it from the **Open positions** list at the current mark price.

The optional **automatic paper trading** toggle opens a trade when a signal
appears — explicitly labelled as simulated automation.

## 8. Risk Management page

Edit limits such as max position size, max risk per trade, daily loss limit,
max open positions, max exposure, and max consecutive losses.

- **Emergency pause** stops new trades.
- **Reset risk lockouts** clears a lockout and records it in the audit log.
- Daily-loss lockouts **persist across restarts**.

## 9. Strategy Lab (backtesting)

Choose parameters, then **Run backtest**. You will see net profit, return, win
rate, profit factor, max drawdown, average win/loss, an equity curve, and every
simulated trade.

Remember: good backtest numbers do **not** guarantee future profit.

## 10. Trade Journal

Every simulated trade is stored in `data/trading_bot.db`. Filter by symbol,
side, status, or strategy and export the result as CSV.

## 11. Settings & Diagnostics

- Provider status and last error.
- App version, database path, log path.
- **Backup database now** (safe copy).
- **Reset paper account** (double confirmation).
- Event/audit log of lockouts and resets.

## 12. Troubleshooting

| Problem | Fix |
|---------|-----|
| `streamlit` not found | Activate `.venv` and reinstall requirements |
| No crypto data | Check internet; enable synthetic fallback |
| Forex data missing | Intraday FX history is limited; try `1h` or `1d` |
| PowerShell blocks activation | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Account looks wrong after crash | Restart the app; state is restored from SQLite |

## 13. Glossary

- **Candle** – price bar showing open/high/low/close for a period.
- **EMA** – exponential moving average; reacts faster than a simple average.
- **RSI** – momentum oscillator from 0–100.
- **MACD** – trend/momentum indicator from two EMAs.
- **Stop-loss** – price to exit and limit a loss (not a guarantee).
- **Take-profit** – price to lock in a gain.
- **Spread / slippage** – real-world costs modelled in the simulator.
- **Notional** – position size × price.