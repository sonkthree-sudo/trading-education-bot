"""Risk management.

Risk controls are mandatory and persist across application restarts. The
manager is pure logic (no I/O); ``PaperAccount`` and the storage layer are
responsible for persisting and restoring its state.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional

from ..utils import utcnow


@dataclass
class RiskConfig:
    max_position_pct: float = 0.05        # max position notional as % of equity
    max_risk_per_trade: float = 0.01      # max estimated loss per trade as % of equity
    stop_loss_pct: float = 0.02           # default stop distance
    take_profit_pct: float = 0.04         # default take-profit distance
    risk_reward: float = 2.0
    daily_loss_limit: float = 0.03        # % of day-start equity
    max_open_positions: int = 1
    max_total_exposure_pct: float = 0.20  # max total notional as % of equity
    max_consecutive_losses: int = 5
    cooldown_candles: int = 3
    emergency_pause: bool = False

    def validate(self) -> "RiskConfig":
        """Raise ValueError on impossible settings."""
        if not (0 < self.max_position_pct <= 1):
            raise ValueError("max_position_pct must be between 0 and 1")
        if not (0 < self.max_risk_per_trade <= 1):
            raise ValueError("max_risk_per_trade must be between 0 and 1")
        if not (0 < self.daily_loss_limit <= 1):
            raise ValueError("daily_loss_limit must be between 0 and 1")
        if self.stop_loss_pct <= 0 or self.take_profit_pct <= 0:
            raise ValueError("stop_loss_pct and take_profit_pct must be > 0")
        if self.risk_reward <= 0:
            raise ValueError("risk_reward must be > 0")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be >= 1")
        if self.max_total_exposure_pct <= 0:
            raise ValueError("max_total_exposure_pct must be > 0")
        if self.max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be >= 1")
        if self.cooldown_candles < 0:
            raise ValueError("cooldown_candles must be >= 0")
        return self


class RiskCheck:
    """Result of a pre-trade risk check."""

    def __init__(self, allowed: bool, reason: str = "OK", details: Optional[Dict[str, Any]] = None):
        self.allowed = allowed
        self.reason = reason
        self.details = details or {}

    def __bool__(self) -> bool:
        return self.allowed

    def __repr__(self) -> str:
        return f"RiskCheck(allowed={self.allowed}, reason={self.reason})"


class RiskManager:
    def __init__(self, config: Optional[RiskConfig] = None, starting_equity: float = 10_000.0):
        self.config = (config or RiskConfig()).validate()
        self.starting_equity = starting_equity
        self.daily_start_equity = starting_equity
        self.daily_realized_pnl = 0.0
        self.daily_unrealized_pnl = 0.0
        self.consecutive_losses = 0
        self.current_day = date.today().isoformat()
        self.emergency_pause = self.config.emergency_pause
        self.lockout_events = []  # audit trail of lockouts / resets

    # -- day handling -------------------------------------------------------
    def roll_day_if_needed(self, current_equity: float, today: Optional[str] = None) -> bool:
        """Reset daily counters when the calendar day changes. Returns True if rolled."""
        today = today or date.today().isoformat()
        if today != self.current_day:
            self.current_day = today
            self.daily_start_equity = current_equity
            self.daily_realized_pnl = 0.0
            self.daily_unrealized_pnl = 0.0
            # A new day clears the daily-loss pause but NOT a manual emergency pause.
            self.lockout_events.append({"time": utcnow().isoformat(), "event": "day_rollover"})
            return True
        return False

    def record_realized(self, pnl: float) -> None:
        self.daily_realized_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        elif pnl > 0:
            self.consecutive_losses = 0

    def set_unrealized(self, pnl: float) -> None:
        self.daily_unrealized_pnl = pnl

    # -- derived metrics ----------------------------------------------------
    @property
    def daily_pnl(self) -> float:
        return self.daily_realized_pnl + self.daily_unrealized_pnl

    def daily_loss(self, current_equity: float) -> float:
        """Positive number representing today's loss (0 if flat/up)."""
        loss = self.daily_start_equity - current_equity
        return max(loss, 0.0)

    def daily_loss_pct(self, current_equity: float) -> float:
        if self.daily_start_equity <= 0:
            return 0.0
        return self.daily_loss(current_equity) / self.daily_start_equity

    def remaining_daily_allowance(self, current_equity: float) -> float:
        limit_amount = self.daily_start_equity * self.config.daily_loss_limit
        return max(limit_amount - self.daily_loss(current_equity), 0.0)

    # -- checks -------------------------------------------------------------
    def check_daily_limit(self, current_equity: float) -> RiskCheck:
        if self.emergency_pause:
            return RiskCheck(False, "Emergency pause is active")
        if self.daily_loss_pct(current_equity) >= self.config.daily_loss_limit:
            return RiskCheck(
                False,
                f"Daily loss limit hit ({self.daily_loss_pct(current_equity)*100:.2f}% "
                f">= {self.config.daily_loss_limit*100:.2f}%)",
            )
        return RiskCheck(True)

    def check_consecutive_losses(self) -> RiskCheck:
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            return RiskCheck(
                False,
                f"Max consecutive losses reached ({self.consecutive_losses})",
            )
        return RiskCheck(True)

    def size_position(
        self,
        equity: float,
        entry_price: float,
        stop_price: float,
        max_position_pct: Optional[float] = None,
    ) -> RiskCheck:
        """Risk-based position sizing.

        The quantity is chosen so that the loss at the stop equals at most
        ``max_risk_per_trade`` of equity, and the resulting notional does not
        exceed ``max_position_pct`` of equity.
        """
        if equity <= 0:
            return RiskCheck(False, "Equity must be > 0", {"quantity": 0.0})
        if entry_price <= 0:
            return RiskCheck(False, "Entry price must be > 0", {"quantity": 0.0})
        if stop_price <= 0 or stop_price == entry_price:
            return RiskCheck(False, "Stop price must be > 0 and differ from entry", {"quantity": 0.0})

        risk_per_unit = abs(entry_price - stop_price)
        risk_amount = equity * self.config.max_risk_per_trade
        qty_by_risk = risk_amount / risk_per_unit

        max_notional = equity * (max_position_pct or self.config.max_position_pct)
        qty_by_notional = max_notional / entry_price

        qty = min(qty_by_risk, qty_by_notional)
        if qty <= 0:
            return RiskCheck(False, "Computed quantity is zero", {"quantity": 0.0})

        details = {
            "quantity": qty,
            "notional": qty * entry_price,
            "risk_at_stop": qty * risk_per_unit,
            "risk_pct": (qty * risk_per_unit) / equity,
            "capped_by": "risk" if qty_by_risk <= qty_by_notional else "notional",
        }
        return RiskCheck(True, "OK", details)

    def evaluate_new_trade(
        self,
        equity: float,
        open_positions: int,
        current_exposure: float,
        trade_notional: float,
    ) -> RiskCheck:
        for check in (
            self.check_daily_limit(equity),
            self.check_consecutive_losses(),
        ):
            if not check:
                return check
        if open_positions >= self.config.max_open_positions:
            return RiskCheck(False, f"Max open positions reached ({self.config.max_open_positions})")
        max_position = equity * self.config.max_position_pct
        if trade_notional > max_position:
            return RiskCheck(
                False,
                f"Position notional {trade_notional:,.2f} exceeds {self.config.max_position_pct*100:.1f}% "
                f"of equity (max {max_position:,.2f})",
            )
        max_exposure = equity * self.config.max_total_exposure_pct
        if current_exposure + trade_notional > max_exposure:
            return RiskCheck(False, f"Total exposure limit reached (max {max_exposure:,.0f})")
        return RiskCheck(True)

    # -- control ------------------------------------------------------------
    def trigger_emergency_pause(self, reason: str = "manual") -> None:
        self.emergency_pause = True
        self.lockout_events.append(
            {"time": utcnow().isoformat(), "event": "emergency_pause", "reason": reason}
        )

    def reset_lockouts(self, reason: str = "manual_reset") -> None:
        self.emergency_pause = False
        self.consecutive_losses = 0
        self.daily_realized_pnl = 0.0
        self.daily_unrealized_pnl = 0.0
        self.lockout_events.append(
            {"time": utcnow().isoformat(), "event": "reset_lockouts", "reason": reason}
        )

    # -- persistence --------------------------------------------------------
    def to_state(self) -> Dict[str, Any]:
        return {
            "daily_start_equity": self.daily_start_equity,
            "daily_realized_pnl": self.daily_realized_pnl,
            "daily_unrealized_pnl": self.daily_unrealized_pnl,
            "consecutive_losses": self.consecutive_losses,
            "current_day": self.current_day,
            "emergency_pause": self.emergency_pause,
            "config": asdict(self.config),
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        self.daily_start_equity = float(state.get("daily_start_equity", self.daily_start_equity))
        self.daily_realized_pnl = float(state.get("daily_realized_pnl", 0.0))
        self.daily_unrealized_pnl = float(state.get("daily_unrealized_pnl", 0.0))
        self.consecutive_losses = int(state.get("consecutive_losses", 0))
        self.current_day = state.get("current_day", self.current_day)
        self.emergency_pause = bool(state.get("emergency_pause", False))
        cfg = state.get("config")
        if cfg:
            merged = asdict(self.config)
            merged.update({k: cfg[k] for k in cfg if k in merged})
            self.config = RiskConfig(**merged).validate()