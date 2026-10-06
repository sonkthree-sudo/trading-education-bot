"""Historical backtesting engine.

Look-ahead-bias protection
--------------------------
A signal is generated using ONLY the candle at index ``i`` (whose close is
known at that moment). The order is executed at the OPEN of candle ``i + 1``.
Stops and take-profits are evaluated on the range (high/low) of the candles
that follow the entry.

Intrabar ambiguity
------------------
With only OHLC candles we cannot know whether the stop or the take-profit was
touched first inside a candle. When both fall inside the same candle we
CONSERVATIVELY assume the STOP LOSS was hit first. This is stated in the UI.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from config import settings

from ..simulation.paper_account import PaperAccount
from ..simulation.risk_manager import RiskConfig
from ..strategies.base_strategy import BaseStrategy
from .performance import PerformanceMetrics


class BacktestEngine:
    def __init__(
        self,
        initial_balance: float = settings.START_BALANCE,
        commission_pct: float = settings.DEFAULT_COMMISSION_PCT,
        slippage_pct: float = settings.DEFAULT_SLIPPAGE_PCT,
        spread_pct: float = settings.DEFAULT_SPREAD_PCT,
        risk_config: Optional[RiskConfig] = None,
    ):
        self.initial_balance = float(initial_balance)
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.spread_pct = spread_pct
        self.risk_config = (risk_config or RiskConfig()).validate()

    def run(
        self,
        df: pd.DataFrame,
        strategy: BaseStrategy,
        market: str = "crypto",
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        allow_short: bool = True,
    ) -> Dict[str, Any]:
        empty = {
            "ok": False,
            "trades": [],
            "equity_curve": [self.initial_balance],
            "metrics": PerformanceMetrics().calculate([], [self.initial_balance], self.initial_balance),
            "error": "Insufficient data for backtest",
        }
        if df is None or len(df) < strategy.min_candles + 2:
            return empty

        prepared = strategy.prepare(df)

        account = PaperAccount(
            initial_balance=self.initial_balance,
            commission_pct=self.commission_pct,
            slippage_pct=self.slippage_pct,
            spread_pct=self.spread_pct,
            risk_config=self.risk_config,
            enforce_one_position_per_symbol=True,
        )

        equity_curve: List[float] = []
        trades: List[Dict[str, Any]] = []
        pending_signal = None
        start = strategy.min_candles

        for i in range(start, len(prepared)):
            candle = prepared.iloc[i]
            price = float(candle["close"])

            # 1) Manage open positions with this candle's range.
            for position in list(account.get_open_positions()):
                exit_price, reason = self._check_exit(position, candle)
                if exit_price is not None:
                    pl = account.close_position(position.id, exit_price, reason)
                    trades.append(position.to_dict())

            # 2) Execute any pending signal at this candle's open.
            if pending_signal is not None and len(account.get_open_positions()) == 0:
                self._execute(account, pending_signal, float(candle["open"]), market, symbol, timeframe, strategy.name)
            pending_signal = None

            # 3) Generate a new signal at this candle's close for the next bar.
            signal = strategy.evaluate(prepared, i)
            if signal.action == "BUY" or (signal.action == "SELL" and allow_short):
                pending_signal = signal

            # 4) Mark-to-market equity.
            equity_curve.append(account.get_equity({symbol: price}))

        # Close any remaining position at the final close (documented behaviour).
        final_price = float(prepared["close"].iloc[-1])
        for position in list(account.get_open_positions()):
            account.close_position(position.id, final_price, "end_of_data")
            trades.append(position.to_dict())

        if equity_curve:
            equity_curve[-1] = account.get_equity()

        metrics = PerformanceMetrics().calculate(trades, equity_curve, self.initial_balance)

        return {
            "ok": True,
            "trades": trades,
            "equity_curve": equity_curve,
            "metrics": metrics,
            "final_account": account,
            "error": None,
        }

    @staticmethod
    def _check_exit(position, candle) -> tuple:
        high = float(candle["high"])
        low = float(candle["low"])
        if position.side == "LONG":
            stop_hit = position.stop_loss is not None and low <= position.stop_loss
            tp_hit = position.take_profit is not None and high >= position.take_profit
            if stop_hit:
                return position.stop_loss, "stop_loss"
            if tp_hit:
                return position.take_profit, "take_profit"
        else:
            stop_hit = position.stop_loss is not None and high >= position.stop_loss
            tp_hit = position.take_profit is not None and low <= position.take_profit
            if stop_hit:
                return position.stop_loss, "stop_loss"
            if tp_hit:
                return position.take_profit, "take_profit"
        return None, ""

    def _execute(self, account, signal, entry_price, market, symbol, timeframe, strategy_name) -> None:
        if entry_price <= 0:
            return
        stop_pct = account.risk_manager.config.stop_loss_pct
        tp_pct = account.risk_manager.config.take_profit_pct
        if signal.action == "BUY":
            side = "LONG"
            stop = entry_price * (1 - stop_pct)
            take = entry_price * (1 + tp_pct)
        else:
            side = "SHORT"
            stop = entry_price * (1 + stop_pct)
            take = entry_price * (1 - tp_pct)

        equity = account.get_equity()
        sizing = account.risk_manager.size_position(equity, entry_price, stop)
        if not sizing:
            return
        qty = sizing.details["quantity"]
        try:
            account.open_position(
                symbol=symbol,
                market=market,
                side=side,
                quantity=qty,
                price=entry_price,
                strategy=strategy_name,
                reason=signal.reason,
                stop_loss=stop,
                take_profit=take,
                timeframe=timeframe,
                force=True,  # historical data does not map to real calendar days
            )
        except ValueError:
            return