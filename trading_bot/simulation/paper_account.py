"""Paper-trading account.

A fully simulated account. There is deliberately NO code path that can send a
real order. Concurrent accounting uses the ``balance`` (realized cash) plus
unrealized P&L of open positions to obtain ``equity``.

Currency notes:
  * Crypto pairs are quoted in USDT, treated 1:1 with the USD account for
    education.
  * For forex pairs whose quote currency is not USD (e.g. USD/JPY), P&L is
    converted to the account currency using the pair's own price, which is a
    reasonable educational approximation and is labelled as such.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import settings
from ..utils import utcnow

from .position_manager import Position
from .risk_manager import RiskCheck, RiskConfig, RiskManager


class PaperAccount:
    def __init__(
        self,
        initial_balance: Optional[float] = None,
        commission_pct: float = settings.DEFAULT_COMMISSION_PCT,
        slippage_pct: float = settings.DEFAULT_SLIPPAGE_PCT,
        spread_pct: float = settings.DEFAULT_SPREAD_PCT,
        risk_config: Optional[RiskConfig] = None,
        enforce_one_position_per_symbol: bool = True,
    ):
        self.initial_balance = float(initial_balance if initial_balance is not None else settings.START_BALANCE)
        if self.initial_balance <= 0:
            raise ValueError("Initial balance must be > 0")
        self.balance = self.initial_balance
        self.commission_pct = float(commission_pct)
        self.slippage_pct = float(slippage_pct)
        self.spread_pct = float(spread_pct)
        self.risk_manager = RiskManager(risk_config, starting_equity=self.initial_balance)
        self.positions: List[Position] = []
        self.closed_positions: List[Position] = []
        self.enforce_one_position_per_symbol = enforce_one_position_per_symbol

    # -- queries ------------------------------------------------------------
    def get_open_positions(self) -> List[Position]:
        return [p for p in self.positions if p.status == "OPEN"]

    def get_position(self, position_id: str) -> Optional[Position]:
        for p in self.positions:
            if p.id == position_id:
                return p
        return None

    def has_open_position(self, symbol: str) -> bool:
        return any(p.symbol == symbol and p.status == "OPEN" for p in self.positions)

    def get_total_exposure(self) -> float:
        return sum(abs(p.quantity * p.entry_price) for p in self.get_open_positions())

    def get_unrealized_pnl(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        prices = current_prices or {}
        total = 0.0
        for p in self.get_open_positions():
            current = float(prices.get(p.symbol, p.entry_price))
            p.unrealized_pnl = self._compute_pnl(p, current) - p.fees
            total += p.unrealized_pnl
        return total

    def get_equity(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        return self.balance + self.get_unrealized_pnl(current_prices)

    def get_used_capital(self) -> float:
        return self.get_total_exposure()

    # -- P&L helpers --------------------------------------------------------
    @staticmethod
    def _quote_currency(symbol: str) -> str:
        if "/" in symbol:
            return symbol.split("/")[1].upper()
        return "USD"

    def _to_account(self, symbol: str, amount: float, reference_price: float) -> Tuple[float, bool]:
        """Convert quote-currency P&L to account currency (USD). Returns (value, approximate)."""
        quote = self._quote_currency(symbol)
        if quote in ("USD", "USDT", "USDC", "BUSD"):
            return amount, False
        if quote == "JPY" and reference_price > 0:
            return amount / reference_price, True
        # Unknown quote currency: mark as approximate (no reliable rate available).
        return amount, True

    def _compute_pnl(self, position: Position, exit_price: float) -> float:
        if position.side == "LONG":
            raw = (exit_price - position.entry_price) * position.quantity
        else:
            raw = (position.entry_price - exit_price) * position.quantity
        value, _approx = self._to_account(position.symbol, raw, exit_price)
        return value

    def _apply_slippage_spread(self, price: float, side: str, opening: bool) -> float:
        """Return an adverse fill price including half-spread and slippage."""
        cost = (self.spread_pct / 2.0) + self.slippage_pct
        is_buy = (side == "LONG" and opening) or (side == "SHORT" and not opening)
        return price * (1 + cost) if is_buy else price * (1 - cost)

    # -- validation ---------------------------------------------------------
    def validate_order(self, symbol: str, side: str, quantity: float, price: float) -> RiskCheck:
        if side not in ("LONG", "SHORT"):
            return RiskCheck(False, f"Invalid side: {side}")
        if quantity is None or quantity <= 0:
            return RiskCheck(False, "Quantity must be > 0")
        if price is None or price <= 0:
            return RiskCheck(False, "Price must be > 0")
        if self.enforce_one_position_per_symbol and self.has_open_position(symbol):
            return RiskCheck(False, f"An open position already exists for {symbol}")
        equity = self.get_equity()
        notional = abs(quantity * price)
        return self.risk_manager.evaluate_new_trade(
            equity=equity,
            open_positions=len(self.get_open_positions()),
            current_exposure=self.get_total_exposure(),
            trade_notional=notional,
        )

    # -- trading ------------------------------------------------------------
    def open_position(
        self,
        symbol: str,
        market: str,
        side: str,
        quantity: float,
        price: float,
        strategy: str = "manual",
        reason: str = "",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        timeframe: str = "",
        force: bool = False,
    ) -> Position:
        if not force:
            check = self.validate_order(symbol, side, quantity, price)
            if not check:
                raise ValueError(check.reason)

        fill = self._apply_slippage_spread(float(price), side, opening=True)
        notional = abs(quantity * fill)
        entry_fee = notional * self.commission_pct
        slippage_cost = abs(fill - price) * quantity

        position = Position(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            market=market,
            side=side,
            quantity=float(quantity),
            entry_price=float(fill),
            entry_time=utcnow(),
            entry_reason=reason,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
            timeframe=timeframe,
            status="OPEN",
            entry_fees=entry_fee,
            fees=entry_fee,
            slippage=slippage_cost,
        )
        self.positions.append(position)
        # Entry commission leaves the cash balance immediately.
        self.balance -= entry_fee
        return position

    def close_position(
        self,
        position_id: str,
        price: float,
        reason: str = "manual",
    ) -> Optional[float]:
        position = self.get_position(position_id)
        if position is None or position.status != "OPEN":
            return None
        if price is None or price <= 0:
            raise ValueError("Exit price must be > 0")

        fill = self._apply_slippage_spread(float(price), position.side, opening=False)
        gross = self._compute_pnl(position, fill)
        exit_notional = abs(position.quantity * fill)
        exit_fee = exit_notional * self.commission_pct
        total_fees = position.entry_fees + exit_fee
        net_pnl = gross - total_fees

        position.exit_price = float(fill)
        position.exit_time = utcnow()
        position.exit_reason = reason
        position.status = "CLOSED"
        position.fees = total_fees
        position.realized_pnl = net_pnl

        self.balance += net_pnl
        self.closed_positions.append(position)
        self.risk_manager.record_realized(net_pnl)
        self.risk_manager.roll_day_if_needed(self.get_equity())
        return net_pnl

    def close_position_by_symbol(self, symbol: str, price: float, reason: str = "manual") -> Optional[float]:
        for p in self.get_open_positions():
            if p.symbol == symbol:
                return self.close_position(p.id, price, reason)
        return None

    def check_stops(self, current_prices: Dict[str, float]) -> List[Tuple[Position, float, str]]:
        """Return positions whose stop/take-profit has been touched.

        When only a close price is available we conservatively exit only when
        the *close* breaches the level. Intrabar ambiguity is documented in docs.
        """
        triggered: List[Tuple[Position, float, str]] = []
        for p in self.get_open_positions():
            price = current_prices.get(p.symbol)
            if price is None:
                continue
            price = float(price)
            if p.stop_loss is not None:
                if (p.side == "LONG" and price <= p.stop_loss) or (p.side == "SHORT" and price >= p.stop_loss):
                    triggered.append((p, price, "stop_loss"))
                    continue
            if p.take_profit is not None:
                if (p.side == "LONG" and price >= p.take_profit) or (p.side == "SHORT" and price <= p.take_profit):
                    triggered.append((p, price, "take_profit"))
        return triggered

    # -- state --------------------------------------------------------------
    def reset_account(self, reason: str = "manual_reset") -> None:
        self.balance = self.initial_balance
        self.positions = []
        self.closed_positions = []
        self.risk_manager = RiskManager(self.risk_manager.config, starting_equity=self.initial_balance)
        self.risk_manager.reset_lockouts(reason)

    def summary(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        equity = self.get_equity(current_prices)
        realized = sum(p.realized_pnl for p in self.closed_positions)
        unrealized = self.get_unrealized_pnl(current_prices)
        wins = [p for p in self.closed_positions if p.realized_pnl > 0]
        win_rate = (len(wins) / len(self.closed_positions) * 100) if self.closed_positions else 0.0
        return {
            "balance": self.balance,
            "equity": equity,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "open_positions": len(self.get_open_positions()),
            "closed_trades": len(self.closed_positions),
            "win_rate": win_rate,
            "exposure": self.get_total_exposure(),
        }