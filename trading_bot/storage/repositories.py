"""Repositories: translate between the paper account and the database."""

from typing import Optional

from .database import Database
from ..simulation.paper_account import PaperAccount
from ..simulation.position_manager import Position


class AccountRepository:
    def __init__(self, db: Database):
        self.db = db

    def save_account(self, account: PaperAccount) -> None:
        self.db.save_account_state(account.balance, account.initial_balance)
        self.db.save_risk_state(account.risk_manager.to_state())
        for position in account.positions:
            self.db.upsert_trade(position.to_dict())

    def load_into(self, account: PaperAccount) -> PaperAccount:
        """Restore balance, positions, and risk state into ``account``."""
        state = self.db.load_account_state()
        if state:
            account.balance = float(state["balance"])
            account.initial_balance = float(state["initial_balance"])

        rows = self.db.get_trades()
        account.positions = []
        account.closed_positions = []
        for row in rows:
            position = Position.from_row(row)
            if position.status == "OPEN":
                account.positions.append(position)
            else:
                account.closed_positions.append(position)

        risk_state = self.db.load_risk_state()
        if risk_state:
            account.risk_manager.load_state(risk_state)
        return account

    def record_trade(self, position: Position) -> None:
        self.db.upsert_trade(position.to_dict())

    def reset(self, account: PaperAccount, reason: str = "manual_reset") -> None:
        self.db.delete_all_trades()
        self.db.clear_account_state()
        account.reset_account(reason)
        self.db.log_event("account_reset", {"reason": reason})
        self.save_account(account)


def build_default_account(db: Optional[Database] = None) -> tuple[PaperAccount, Database]:
    """Create a fresh account and database, restoring prior state if present."""
    db = db or Database()
    account = PaperAccount()
    repo = AccountRepository(db)
    repo.load_into(account)
    return account, db