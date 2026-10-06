# Trading Education Bot

An educational cryptocurrency **and** forex trading simulator for learning
technical analysis, trading signals, risk management, paper trading, and
strategy backtesting — without risking real money.

> **This is an educational tool, not financial advice.**
> The default and only operating mode is **PAPER TRADING**.
> It cannot place real orders, cannot use private API keys, and never claims
> that a signal guarantees a profit.

---

## 1. What it does

- Loads public market data (crypto via CCXT/Binance, forex via yfinance).
- Falls back to clearly-labelled **synthetic** data when offline.
- Computes indicators (EMA, RSI, MACD, Bollinger Bands, ATR) with **no
  look-ahead bias**.
- Detects and explains candlestick patterns.
- Produces **explainable** BUY / SELL / WAIT signals.
- Simulates a $10,000 paper account with long and short positions, commission,
  spread, and slippage.
- Enforces persistent **risk controls** (position sizing, daily loss limit,
  max exposure, consecutive-loss lockouts).
- Backtests a strategy over history with transparent metrics.
- Stores every simulated trade in SQLite and lets you export to CSV.

## 2. Safety boundaries

- There is **no real order execution** anywhere in the codebase.
- No exchange/broker private keys are used or requested.
- No withdrawals, deposits, or live-account integration.
- Synthetic data is always visually labelled and never presented as real.
- Daily-loss lockouts persist across restarts and cannot be cleared by
  refreshing the dashboard.

## 3. Requirements

- Windows 10/11 (also works on macOS/Linux) with VS Code.
- Python 3.10+ (developed on 3.12).
- Internet access is optional — the synthetic fallback works fully offline.

## 4. Installation (Windows PowerShell)

```powershell
cd D:\Projects\trading-education-bot

# Create a virtual environment (skip if .venv already exists)
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 5. Run the dashboard

```powershell
streamlit run app.py
```

Your browser opens at `http://localhost:8501`.

## 6. Run the tests

```powershell
python -m pytest
```

Expected: **62 tests pass**. Tests are deterministic and never require the
internet.

## 7. Project structure

```
trading-education-bot/
  app.py                         # Streamlit dashboard (all pages)
  config/settings.py             # Central configuration / defaults
  requirements.txt
  pytest.ini
  conftest.py
  trading_bot/
    logger.py  utils.py
    market_data/   base.py, crypto.py, forex.py, synthetic.py
    indicators/    technical_indicators.py, candlestick_patterns.py
    strategies/    base_strategy.py, ema_rsi_strategy.py, strategy_manager.py
    simulation/    paper_account.py, risk_manager.py, position_manager.py,
                   order_simulator.py
    backtesting/   engine.py, performance.py
    storage/       database.py, repositories.py
    services/      market_service.py, signal_service.py
  tests/                          # 7 test modules, 62 tests
  docs/                           # USER_GUIDE, STRATEGY_GUIDE, RISK_MANAGEMENT
  data/                           # SQLite database (git-ignored)
  logs/                           # application log (git-ignored)
```

## 8. Dashboard pages

- **Overview** – account, equity, P&L, risk status, latest signal.
- **Market Explorer** – symbols, timeframes, recent candles, data provenance.
- **Chart** – candlesticks, EMA9/21/50, RSI, MACD, optional Bollinger Bands.
- **Signal Center** – explainable signals and detected candlestick patterns.
- **Paper Trading** – manual/automatic simulated orders, open positions.
- **Risk Management** – edit limits, see lockout status, reset (audited).
- **Strategy Lab** – configure and run a backtest with full metrics.
- **Trade Journal** – all trades in SQLite with filters and CSV export.
- **Learning Center** – beginner explanations of every concept used.
- **Settings & Diagnostics** – provider status, backups, reset, event log.

## 9. Data sources and their limits

| Source | Used for | Notes |
|--------|----------|-------|
| CCXT / Binance public | Crypto OHLCV | Public only, rate-limited, no keys |
| yfinance (Yahoo) | Forex OHLCV | Educational/historical, may be delayed or incomplete; **not** a broker feed |
| Synthetic | Offline fallback | **Artificial**; reproducible; never real data |

When a real provider fails, the app falls back to synthetic data and labels it
clearly. It never fabricates data while claiming it is real.

## 10. Currency / P&L notes

- Crypto pairs are quoted in USDT, treated 1:1 with the USD account for
  education.
- For forex pairs whose quote currency is not USD (e.g. `USD/JPY`), P&L is
  converted using the pair's own price — an educational approximation, and it
  is marked as approximate internally.

## 11. Backtesting assumptions

- A signal is computed from the candle **at** index `i` (close known) and the
  order is executed at the **open of candle `i + 1`** — no look-ahead.
- Stops/targets are checked on subsequent candle ranges.
- If a single candle touches **both** stop and target, the **stop** is assumed
  hit first (conservative).
- Commission, spread, and slippage are always applied.
- Backtest results **do not** predict future performance.

## 12. Database and backup

- SQLite file: `data/trading_bot.db`.
- The account is **never reset automatically** on startup.
- Back up from **Settings & Diagnostics → Backup database now** (uses SQLite's
  safe backup API), or copy the `.db` file while the app is closed.

## 13. Known limitations

- Forex intraday history from yfinance is limited and may contain gaps.
- Crypto data requires internet; the public endpoint may be rate-limited or
  blocked in some regions (synthetic fallback then applies).
- The bundled strategy is intentionally simple and educational.
- Only close-based stop checking is used for live paper trades; the backtester
  uses high/low ranges with the documented conservative rule.
- One open position per symbol is enforced by default.

## 14. Disclaimer

This software is for education only. It is not financial advice. Trading
involves substantial risk. Past performance — real or simulated — does not
guarantee future results.