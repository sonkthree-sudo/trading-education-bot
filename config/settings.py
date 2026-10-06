"""Central configuration for the Trading Education Bot.

Every value here is a sensible, conservative default for an educational
paper-trading simulator. Nothing in this file (or anywhere in the project)
can place a real order or touch a real brokerage account.
"""

from pathlib import Path

# --- Application -----------------------------------------------------------
APP_NAME = "Trading Education Bot"
APP_VERSION = "1.0.0"
UTC = True

# --- Paths -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
DB_PATH = str(DATA_DIR / "trading_bot.db")
LOG_PATH = str(LOG_DIR / "app.log")

# --- Paper account defaults ------------------------------------------------
START_BALANCE = 10_000.0

# --- Risk defaults (conservative, educational) -----------------------------
DEFAULT_MAX_POSITION = 0.05      # 5% of equity as max position notional
DEFAULT_RISK_PER_TRADE = 0.01    # 1% of equity risked per trade
DEFAULT_STOP_LOSS_PCT = 0.02     # 2% stop distance
DEFAULT_TAKE_PROFIT_PCT = 0.04   # 4% take-profit distance (2:1 RR)
DEFAULT_RISK_REWARD = 2.0
DEFAULT_DAILY_LOSS_LIMIT = 0.03  # 3% of day-start equity
DEFAULT_MAX_OPEN_POSITIONS = 1
DEFAULT_MAX_CONSECUTIVE_LOSSES = 5
DEFAULT_COOLDOWN_CANDLES = 3

# --- Transaction cost defaults ---------------------------------------------
DEFAULT_COMMISSION_PCT = 0.0005  # 0.05% per side
DEFAULT_SLIPPAGE_PCT = 0.0005    # 0.05%
DEFAULT_SPREAD_PCT = 0.0001      # 0.01%

# --- Market data -----------------------------------------------------------
DEFAULT_CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
DEFAULT_FOREX_SYMBOLS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]
DEFAULT_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
DEFAULT_TIMEFRAME = "1h"
DEFAULT_CANDLE_LIMIT = 500