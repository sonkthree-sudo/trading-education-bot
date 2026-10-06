"""Order simulator.

Thin convenience wrapper around ``PaperAccount`` that makes the safety
boundary explicit: it can only ever open *simulated* positions.
"""

from typing import Optional

from .paper_account import PaperAccount
from .position_manager import Position


class OrderSimulator:
    def __init__(self, account: PaperAccount):
        self.account = account

    def market_buy(self, symbol: str, market: str, quantity: float, price: float, **kwargs) -> Position:
        return self.account.open_position(symbol, market, "LONG", quantity, price, **kwargs)

    def market_sell(self, symbol: str, market: str, quantity: float, price: float, **kwargs) -> Position:
        return self.account.open_position(symbol, market, "SHORT", quantity, price, **kwargs)

    def close(self, position_id: str, price: float, reason: str = "manual") -> Optional[float]:
        return self.account.close_position(position_id, price, reason)