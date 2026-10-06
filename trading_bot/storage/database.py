"""SQLite persistence layer.

The schema is initialized safely with ``CREATE TABLE IF NOT EXISTS`` so an
existing database is never destroyed. Account state is loaded on startup and
never reset automatically.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings
from ..utils import utcnow


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or settings.DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                market TEXT,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_time TEXT,
                entry_reason TEXT,
                stop_loss REAL,
                take_profit REAL,
                strategy TEXT,
                timeframe TEXT,
                status TEXT NOT NULL,
                exit_price REAL,
                exit_time TEXT,
                exit_reason TEXT,
                entry_fees REAL DEFAULT 0,
                fees REAL DEFAULT 0,
                slippage REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                notes TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                balance REAL NOT NULL,
                initial_balance REAL NOT NULL,
                updated_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state_json TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                event TEXT NOT NULL,
                details TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_configs (
                name TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    # -- trades -------------------------------------------------------------
    def upsert_trade(self, trade: Dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO trades (
                id, symbol, market, side, quantity, entry_price, entry_time,
                entry_reason, stop_loss, take_profit, strategy, timeframe,
                status, exit_price, exit_time, exit_reason, entry_fees, fees,
                slippage, realized_pnl, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.get("id"),
                trade.get("symbol"),
                trade.get("market"),
                trade.get("side"),
                trade.get("quantity"),
                trade.get("entry_price"),
                _dt(trade.get("entry_time")),
                trade.get("entry_reason"),
                trade.get("stop_loss"),
                trade.get("take_profit"),
                trade.get("strategy"),
                trade.get("timeframe"),
                trade.get("status"),
                trade.get("exit_price"),
                _dt(trade.get("exit_time")),
                trade.get("exit_reason"),
                trade.get("entry_fees", 0.0),
                trade.get("fees", 0.0),
                trade.get("slippage", 0.0),
                trade.get("realized_pnl", 0.0),
                trade.get("notes", ""),
            ),
        )
        self.conn.commit()

    def get_trades(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if status:
            cur.execute("SELECT * FROM trades WHERE status = ? ORDER BY entry_time", (status,))
        else:
            cur.execute("SELECT * FROM trades ORDER BY entry_time")
        return [dict(r) for r in cur.fetchall()]

    def delete_all_trades(self) -> None:
        self.conn.execute("DELETE FROM trades")
        self.conn.commit()

    # -- account ------------------------------------------------------------
    def save_account_state(self, balance: float, initial_balance: float) -> None:
        self.conn.execute(
            """
            INSERT INTO account_state (id, balance, initial_balance, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                balance = excluded.balance,
                initial_balance = excluded.initial_balance,
                updated_at = excluded.updated_at
            """,
            (balance, initial_balance, utcnow().isoformat()),
        )
        self.conn.commit()

    def load_account_state(self) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute("SELECT * FROM account_state WHERE id = 1")
        row = cur.fetchone()
        return dict(row) if row else None

    def clear_account_state(self) -> None:
        self.conn.execute("DELETE FROM account_state")
        self.conn.commit()

    # -- risk ---------------------------------------------------------------
    def save_risk_state(self, state: Dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO risk_state (id, state_json, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (json.dumps(state), utcnow().isoformat()),
        )
        self.conn.commit()

    def load_risk_state(self) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute("SELECT state_json FROM risk_state WHERE id = 1")
        row = cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row["state_json"])
        except Exception:
            return None

    # -- events -------------------------------------------------------------
    def log_event(self, event: str, details: Any = None) -> None:
        self.conn.execute(
            "INSERT INTO app_events (time, event, details) VALUES (?, ?, ?)",
            (
                utcnow().isoformat(),
                event,
                json.dumps(details) if details is not None else None,
            ),
        )
        self.conn.commit()

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT * FROM app_events ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]

    # -- strategy configs ---------------------------------------------------
    def save_strategy_config(self, name: str, config: Dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO strategy_configs (name, config_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                config_json = excluded.config_json,
                updated_at = excluded.updated_at
            """,
            (name, json.dumps(config), utcnow().isoformat()),
        )
        self.conn.commit()

    def load_strategy_config(self, name: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT config_json FROM strategy_configs WHERE name = ?", (name,)
        )
        row = cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row["config_json"])
        except Exception:
            return None

    # -- maintenance --------------------------------------------------------
    def backup_to(self, path: str) -> str:
        """Copy the database to ``path`` using SQLite's safe backup API."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        dest = sqlite3.connect(path)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
        return path


def _dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)