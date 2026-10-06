"""Performance metrics for backtests and the paper account."""

from typing import Any, Dict, List

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    """Maximum drawdown as a negative percentage (0 if no equity data)."""
    if equity is None or len(equity) == 0:
        return 0.0
    equity = pd.Series(equity).astype(float)
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max.replace(0.0, np.nan)
    dd = drawdown.min()
    return float(dd * 100) if pd.notna(dd) else 0.0


class PerformanceMetrics:
    def calculate(
        self,
        trades: List[Dict[str, Any]],
        equity_curve,
        initial_balance: float,
        periods_per_year: int = 0,
    ) -> Dict[str, Any]:
        equity = pd.Series(equity_curve).astype(float) if equity_curve is not None and len(equity_curve) else pd.Series([initial_balance])

        closed = [t for t in trades if t.get("status") == "CLOSED"]
        pnls = [float(t.get("realized_pnl") or 0.0) for t in closed]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        gross_profit = float(sum(wins)) if wins else 0.0
        gross_loss = float(abs(sum(losses))) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

        final_equity = float(equity.iloc[-1])
        net_profit = final_equity - initial_balance
        total_return = (net_profit / initial_balance * 100.0) if initial_balance else 0.0

        durations = [t.get("duration") for t in closed if t.get("duration") is not None]
        avg_duration = float(np.mean(durations)) if durations else 0.0

        expectancy = float(np.mean(pnls)) if pnls else 0.0

        # Annualised Sharpe-like ratio when we know bars per year.
        sharpe = 0.0
        returns = equity.pct_change().dropna()
        if periods_per_year and len(returns) > 1 and returns.std() > 0:
            sharpe = float((returns.mean() / returns.std()) * np.sqrt(periods_per_year))

        return {
            "initial_balance": float(initial_balance),
            "final_equity": final_equity,
            "net_profit": net_profit,
            "total_return_pct": total_return,
            "total_trades": len(closed),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": (len(wins) / len(closed) * 100.0) if closed else 0.0,
            "profit_factor": profit_factor,
            "average_win": float(np.mean(wins)) if wins else 0.0,
            "average_loss": float(np.mean(losses)) if losses else 0.0,
            "largest_win": float(max(wins)) if wins else 0.0,
            "largest_loss": float(min(losses)) if losses else 0.0,
            "expectancy": expectancy,
            "max_drawdown_pct": max_drawdown(equity),
            "average_duration_seconds": avg_duration,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "sharpe_like": sharpe,
        }