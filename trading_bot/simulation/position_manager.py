"""Position data model shared by the simulator and the backtester."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Position:
    id: str
    symbol: str
    market: str                      # "crypto" or "forex"
    side: str                        # "LONG" or "SHORT"
    quantity: float
    entry_price: float
    entry_time: datetime
    entry_reason: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = "manual"
    timeframe: str = ""
    status: str = "OPEN"             # OPEN | CLOSED
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: str = ""
    fees: float = 0.0                # total fees paid (entry + exit)
    entry_fees: float = 0.0
    slippage: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    notes: str = ""

    @property
    def notional(self) -> float:
        return abs(self.quantity * self.entry_price)

    @property
    def duration(self) -> Optional[float]:
        """Trade duration in seconds, if the trade is closed."""
        if self.exit_time and self.entry_time:
            return (self.exit_time - self.entry_time).total_seconds()
        return None

    def duration_str(self) -> str:
        secs = self.duration
        if secs is None:
            return "-"
        secs = int(secs)
        if secs < 3600:
            return f"{secs // 60}m {secs % 60}s"
        if secs < 86400:
            return f"{secs // 3600}h {(secs % 3600) // 60}m"
        return f"{secs // 86400}d {(secs % 86400) // 3600}h"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for key in ("entry_time", "exit_time"):
            val = d.get(key)
            if isinstance(val, datetime):
                d[key] = val.isoformat()
        d["notional"] = self.notional
        d["duration"] = self.duration
        return d

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Position":
        def parse(value):
            if value in (None, "", "None"):
                return None
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(str(value))
            except Exception:
                return None

        return cls(
            id=row["id"],
            symbol=row["symbol"],
            market=row.get("market", "crypto"),
            side=row["side"],
            quantity=float(row["quantity"]),
            entry_price=float(row["entry_price"]),
            entry_time=parse(row.get("entry_time")),
            entry_reason=row.get("entry_reason", row.get("reason", "")),
            stop_loss=float(row["stop_loss"]) if row.get("stop_loss") not in (None, "") else None,
            take_profit=float(row["take_profit"]) if row.get("take_profit") not in (None, "") else None,
            strategy=row.get("strategy", "manual"),
            timeframe=row.get("timeframe", ""),
            status=row.get("status", "CLOSED"),
            exit_price=float(row["exit_price"]) if row.get("exit_price") not in (None, "") else None,
            exit_time=parse(row.get("exit_time")),
            exit_reason=row.get("exit_reason", ""),
            fees=float(row.get("fees") or 0.0),
            entry_fees=float(row.get("entry_fees") or 0.0),
            slippage=float(row.get("slippage") or 0.0),
            realized_pnl=float(row.get("realized_pnl") or 0.0),
        )