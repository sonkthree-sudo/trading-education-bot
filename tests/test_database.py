import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_bot.simulation.paper_account import PaperAccount
from trading_bot.storage.database import Database
from trading_bot.storage.repositories import AccountRepository, build_default_account


def make_db():
    path = tempfile.mktemp(suffix=".db")
    return Database(path), path


def test_schema_initialization():
    db, path = make_db()
    assert db.get_trades() == []
    db.close()
    Path(path).unlink(missing_ok=True)


def test_trade_persistence_roundtrip():
    db, path = make_db()
    db.upsert_trade(
        {
            "id": "t1",
            "symbol": "BTC/USDT",
            "market": "crypto",
            "side": "LONG",
            "quantity": 1.0,
            "entry_price": 100.0,
            "entry_time": "2023-01-01T00:00:00",
            "strategy": "EMA_RSI",
            "status": "CLOSED",
            "exit_price": 110.0,
            "exit_time": "2023-01-01T01:00:00",
            "realized_pnl": 10.0,
        }
    )
    trades = db.get_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "BTC/USDT"
    assert trades[0]["realized_pnl"] == 10.0
    db.close()
    Path(path).unlink(missing_ok=True)


def test_account_persistence_and_restart():
    db, path = make_db()
    account = PaperAccount(10000.0, commission_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    repo = AccountRepository(db)
    pos = account.open_position("BTC/USDT", "crypto", "LONG", 1.0, 100.0)
    account.close_position(pos.id, 110.0)
    repo.save_account(account)

    # Simulate a restart: brand new account loaded from the same DB.
    fresh = PaperAccount(10000.0)
    repo.load_into(fresh)
    assert len(fresh.closed_positions) == 1
    assert fresh.closed_positions[0].realized_pnl == 10.0
    db.close()
    Path(path).unlink(missing_ok=True)


def test_risk_state_persists_across_restart():
    db, path = make_db()
    account = PaperAccount(10000.0)
    repo = AccountRepository(db)
    account.risk_manager.trigger_emergency_pause("test_lockout")
    repo.save_account(account)

    fresh = PaperAccount(10000.0)
    repo.load_into(fresh)
    assert fresh.risk_manager.emergency_pause is True
    db.close()
    Path(path).unlink(missing_ok=True)


def test_open_position_persists():
    db, path = make_db()
    account = PaperAccount(10000.0)
    repo = AccountRepository(db)
    account.open_position("ETH/USDT", "crypto", "SHORT", 0.2, 2000.0)
    repo.save_account(account)

    fresh = PaperAccount(10000.0)
    repo.load_into(fresh)
    assert len(fresh.get_open_positions()) == 1
    assert fresh.get_open_positions()[0].symbol == "ETH/USDT"
    db.close()
    Path(path).unlink(missing_ok=True)


def test_reset_clears_state():
    db, path = make_db()
    account = PaperAccount(10000.0)
    repo = AccountRepository(db)
    account.open_position("BTC/USDT", "crypto", "LONG", 0.1, 100.0)
    repo.save_account(account)
    repo.reset(account)
    assert account.get_open_positions() == []
    assert db.get_trades() == []
    db.close()
    Path(path).unlink(missing_ok=True)


def test_events_are_logged():
    db, path = make_db()
    db.log_event("test_event", {"value": 1})
    events = db.get_events()
    assert any(e["event"] == "test_event" for e in events)
    db.close()
    Path(path).unlink(missing_ok=True)