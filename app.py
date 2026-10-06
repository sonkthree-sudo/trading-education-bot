"""Trading Education Bot - Streamlit dashboard.

EDUCATIONAL, PAPER-TRADING ONLY. This application cannot and does not place
real orders. It works without any API credentials. Only public market data is
requested when online; otherwise a clearly-labelled synthetic fallback is used.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from config import settings
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.backtesting.performance import PerformanceMetrics, max_drawdown
from trading_bot.indicators.candlestick_patterns import PATTERN_DESCRIPTIONS
from trading_bot.services.market_service import MarketService
from trading_bot.services.signal_service import SignalService
from trading_bot.simulation.risk_manager import RiskConfig
from trading_bot.storage.database import Database
from trading_bot.storage.repositories import AccountRepository, build_default_account
from trading_bot.strategies.strategy_manager import get_strategy
from trading_bot.utils import utcnow

st.set_page_config(
    page_title=settings.APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)

COLOR_UP = "#26a69a"
COLOR_DOWN = "#ef5350"


# --------------------------------------------------------------------------
# Session / resource helpers
# --------------------------------------------------------------------------
def init_state() -> None:
    if "db" not in st.session_state:
        st.session_state.db = Database()
    if "account" not in st.session_state:
        account, _ = build_default_account(st.session_state.db)
        st.session_state.account = account
        st.session_state.repo = AccountRepository(st.session_state.db)
    if "market_service" not in st.session_state:
        st.session_state.market_service = MarketService()
    if "signal_service" not in st.session_state:
        st.session_state.signal_service = SignalService()
    if "confirm_reset" not in st.session_state:
        st.session_state.confirm_reset = False
    if "auto_trade" not in st.session_state:
        st.session_state.auto_trade = False


def persist() -> None:
    st.session_state.repo.save_account(st.session_state.account)


@st.cache_data(ttl=300, show_spinner=False)
def load_market_data(market, symbol, timeframe, limit, force_synthetic):
    service = MarketService()
    result = service.get_data(
        market=market,
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        force_synthetic=force_synthetic,
    )
    return result


def get_data(market, symbol, timeframe, limit, force_synthetic):
    result = load_market_data(market, symbol, timeframe, limit, force_synthetic)
    return result


def utc_str(ts) -> str:
    if ts is None:
        return "N/A"
    try:
        return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
def sidebar(service: MarketService):
    st.sidebar.title(settings.APP_NAME)
    st.sidebar.caption(f"v{settings.APP_VERSION} - PAPER TRADING ONLY")

    page = st.sidebar.radio(
        "Navigation",
        [
            "Overview",
            "Market Explorer",
            "Chart",
            "Signal Center",
            "Paper Trading",
            "Risk Management",
            "Strategy Lab",
            "Trade Journal",
            "Learning Center",
            "Settings & Diagnostics",
        ],
    )

    st.sidebar.divider()
    st.sidebar.subheader("Market")
    market = st.sidebar.selectbox("Market", ["crypto", "forex"], index=0)
    symbols = service.symbols_for(market)
    symbol = st.sidebar.selectbox("Symbol", symbols, index=0)
    timeframe = st.sidebar.selectbox(
        "Timeframe", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"], index=4
    )
    limit = st.sidebar.slider("Candles", 100, 1000, 500, step=50)
    force_synthetic = st.sidebar.checkbox("Force synthetic data (offline)", value=False)

    if market == "forex":
        st.sidebar.info(
            "Forex data comes from Yahoo Finance. It is historical/educational "
            "only, may be delayed, and is not a real-time broker feed."
        )

    return {
        "page": page,
        "market": market,
        "symbol": symbol,
        "timeframe": timeframe,
        "limit": limit,
        "force_synthetic": force_synthetic,
    }


# --------------------------------------------------------------------------
# Shared widgets
# --------------------------------------------------------------------------
def data_status_banner(result) -> None:
    if not result.ok:
        st.error(f"Could not load data from {result.source}: {result.error}")
        return
    freshness = utc_str(result.last_time)
    cols = st.columns([3, 1])
    with cols[0]:
        if result.is_synthetic:
            st.warning(
                "SYNTHETIC DATA in use - artificial, generated prices for "
                "offline learning. NOT real market data."
            )
        else:
            st.success(f"Live/historical data from: {result.source}")
    with cols[1]:
        st.metric("Last candle (UTC)", freshness)
    for warning in result.warnings:
        st.caption(f"Data note: {warning}")


def run_signal_panel(df, symbol, timeframe):
    st.subheader("Latest explainable signal")
    with st.expander("Strategy parameters", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        ema_fast = c1.number_input("EMA fast", 2, 100, 9)
        ema_slow = c2.number_input("EMA slow", 3, 200, 21)
        rsi_period = c3.number_input("RSI period", 2, 50, 14)
        use_trend = c4.checkbox("Use EMA50 trend filter", value=False)
        c5, c6 = st.columns(2)
        rsi_low = c5.number_input("RSI lower bound", 0, 100, 30)
        rsi_high = c6.number_input("RSI upper bound", 0, 100, 70)

    signal = st.session_state.signal_service.generate_signal(
        df,
        strategy_name="EMA_RSI",
        ema_fast=int(ema_fast),
        ema_slow=int(ema_slow),
        rsi_period=int(rsi_period),
        rsi_oversold=float(rsi_low),
        rsi_overbought=float(rsi_high),
        use_trend_filter=bool(use_trend),
    )
    action = signal.action
    if action == "BUY":
        st.success(f"BUY signal - {signal.reason}")
    elif action == "SELL":
        st.error(f"SELL signal - {signal.reason}")
    else:
        st.info(f"WAIT - {signal.reason}")
    cols = st.columns(3)
    cols[0].metric("Signal action", action)
    cols[1].metric("Price at signal", f"{signal.price:,.4f}" if signal.price else "N/A")
    cols[2].metric("Candle time (UTC)", utc_str(signal.timestamp))
    if signal.indicators:
        st.caption("Indicators at this candle: " + ", ".join(f"{k}={v}" for k, v in signal.indicators.items()))
    st.caption(
        "An entry signal is not an instruction to trade. Signals are generated "
        "only after a candle closes and never guarantee a profit."
    )
    return signal


def candlestick_figure(df, show_bb=False, patterns=None):
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=("Price", "RSI (14)", "MACD"),
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_color=COLOR_UP,
            decreasing_line_color=COLOR_DOWN,
        ),
        row=1,
        col=1,
    )
    for col, color in (("ema9", "#29b6f6"), ("ema21", "#ffa726"), ("ema50", "#ab47bc")):
        if col in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df[col], name=col.upper(), line=dict(color=color, width=1)),
                row=1,
                col=1,
            )
    if show_bb and "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], name="BB upper", line=dict(color="#78909c", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], name="BB lower", line=dict(color="#78909c", width=1, dash="dot")), row=1, col=1)

    if "rsi14" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["rsi14"], name="RSI", line=dict(color="#e040fb")), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color=COLOR_DOWN, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color=COLOR_UP, row=2, col=1)
        fig.update_yaxes(range=[0, 100], row=2, col=1)

    if "macd" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD", line=dict(color="#29b6f6")), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Signal", line=dict(color="#ffa726")), row=3, col=1)
        colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["macd_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], name="Histogram", marker_color=colors), row=3, col=1)

    if patterns:
        for event in patterns:
            fig.add_trace(
                go.Scatter(
                    x=[event["timestamp"]],
                    y=[event["close"]],
                    mode="markers+text",
                    text=[event["pattern"]],
                    textposition="top center",
                    marker=dict(size=9, color="#ffd54f", symbol="star"),
                    name=event["pattern"],
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

    fig.update_layout(
        height=760,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def equity_curve_figure(equity):
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity, mode="lines", name="Equity", line=dict(color="#26a69a")))
    fig.update_layout(height=320, template="plotly_dark", title="Equity curve")
    return fig


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def page_overview(sb, result, signal):
    st.header("Overview")
    account = st.session_state.account
    df = result.df if result.ok else None
    prices = {result.symbol: result.last_price} if result.last_price else {}
    equity = account.get_equity(prices)
    unrealized = account.get_unrealized_pnl(prices)
    realized = sum(p.realized_pnl for p in account.closed_positions)
    closed = account.closed_positions
    wins = [p for p in closed if p.realized_pnl > 0]
    win_rate = (len(wins) / len(closed) * 100) if closed else 0.0

    if df is not None:
        equity_series = pd.Series([account.initial_balance, equity])
        dd = max_drawdown(equity_series)
    else:
        dd = 0.0

    c = st.columns(4)
    c[0].metric("Account balance (cash)", f"${account.balance:,.2f}")
    c[1].metric("Equity", f"${equity:,.2f}")
    c[2].metric("Realized P&L", f"${realized:,.2f}")
    c[3].metric("Unrealized P&L", f"${unrealized:,.2f}")

    c2 = st.columns(4)
    c2[0].metric("Open positions", len(account.get_open_positions()))
    c2[1].metric("Closed trades", len(closed))
    c2[2].metric("Win rate", f"{win_rate:.1f}%")
    c2[3].metric("Max drawdown (session)", f"{dd:.2f}%")

    rm = account.risk_manager
    c3 = st.columns(3)
    c3[0].metric("Daily loss (est.)", f"${rm.daily_loss(equity):,.2f}")
    c3[1].metric("Remaining daily allowance", f"${rm.remaining_daily_allowance(equity):,.2f}")
    status = "PAUSED" if rm.emergency_pause else "ACTIVE"
    c3[2].metric("Risk status", status)

    st.divider()
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Selected market")
        if result.ok:
            st.write(
                f"**{result.symbol}** ({result.market}, {result.timeframe}) - "
                f"last price **{result.last_price:,.4f}** at {utc_str(result.last_time)}"
            )
            st.caption(f"Data source: {result.source}{' (SYNTHETIC)' if result.is_synthetic else ''}")
        else:
            st.warning(f"No data available: {result.error}")
        st.subheader("Latest signal")
        if signal:
            st.write(f"**{signal.action}** - {signal.reason}")
    with right:
        st.subheader("Recent trades")
        recent = sorted(account.closed_positions, key=lambda p: p.exit_time or datetime.min, reverse=True)[:5]
        if recent:
            for p in recent:
                st.write(f"{p.symbol} {p.side} - P&L ${p.realized_pnl:,.2f} ({p.exit_reason})")
        else:
            st.caption("No closed trades yet")


def page_market_explorer(sb, service):
    st.header("Market Explorer")
    st.write("Browse available symbols, timeframes, and the latest candles.")
    data = service.get_data(sb["market"], sb["symbol"], sb["timeframe"], sb["limit"], sb["force_synthetic"])
    data_status_banner(data)
    if not data.ok:
        return None
    st.caption(f"{len(data.df)} candles loaded. Displaying the most recent 15.")
    display = data.df.tail(15).copy()
    display.index = display.index.astype(str)
    st.dataframe(display, use_container_width=True)
    return data


def page_chart(sb, result):
    st.header("Interactive Chart")
    if not result.ok:
        st.warning(f"No data to chart: {result.error}")
        return
    show_bb = st.checkbox("Show Bollinger Bands", value=False)
    show_patterns = st.checkbox("Mark candlestick patterns", value=True)
    df = st.session_state.signal_service.compute_indicators(result.df)
    patterns = st.session_state.signal_service.patterns(result.df) if show_patterns else []
    st.plotly_chart(candlestick_figure(df, show_bb=show_bb, patterns=patterns), use_container_width=True)
    st.caption(
        "Indicators are only shown once enough candles exist; early values are blank. "
        "All timestamps are UTC. A data-freshness indicator is shown in the status banner."
    )


def page_signal_center(sb, result):
    st.header("Signal Center")
    if not result.ok:
        st.warning(f"No data: {result.error}")
        return
    signal = run_signal_panel(result.df, sb["symbol"], sb["timeframe"])

    st.divider()
    st.subheader("Detected candlestick patterns")
    events = st.session_state.signal_service.patterns(result.df, tail=5)
    if not events:
        st.info("No patterns detected in the recent data.")
    for event in reversed(events):
        with st.expander(f"{event['pattern']} at {utc_str(event['timestamp'])}"):
            st.write(f"**Conditions:** {event['conditions']}")
            st.write(f"**Why it may matter:** {event['why']}")
            st.write(f"**Limitations:** {event['limitations']}")


def page_paper_trading(sb, result):
    st.header("Paper Trading Simulator")
    st.caption("All trades here are simulated. No real orders are ever sent.")
    account = st.session_state.account
    df = result.df if result.ok else None
    price = result.last_price

    if not result.ok or price is None:
        st.warning("Load market data before trading.")
        return

    c = st.columns(3)
    c[0].metric("Cash", f"${account.balance:,.2f}")
    c[1].metric("Equity", f"${account.get_equity({result.symbol: price}):,.2f}")
    c[2].metric("Open positions", len(account.get_open_positions()))

    st.divider()
    st.subheader("Manual paper order")
    rm = account.risk_manager
    cols = st.columns(4)
    side = cols[0].selectbox("Side", ["LONG", "SHORT"])
    stop_pct = cols[1].number_input("Stop loss %", 0.1, 50.0, float(rm.config.stop_loss_pct * 100), step=0.1) / 100
    tp_pct = cols[2].number_input("Take profit %", 0.1, 100.0, float(rm.config.take_profit_pct * 100), step=0.1) / 100
    sizing_basis = cols[3].selectbox("Quantity basis", ["Risk-based", "Fixed notional"])

    entry_price = float(price)
    if side == "LONG":
        stop_price = entry_price * (1 - stop_pct)
        tp_price = entry_price * (1 + tp_pct)
    else:
        stop_price = entry_price * (1 + stop_pct)
        tp_price = entry_price * (1 - tp_pct)

    if sizing_basis == "Risk-based":
        sizing = rm.size_position(account.get_equity({result.symbol: entry_price}), entry_price, stop_price)
        if sizing:
            qty = sizing.details["quantity"]
            st.caption(
                f"Risk-based size: {qty:.6f} units, notional ${sizing.details['notional']:,.2f}, "
                f"risk at stop ${sizing.details['risk_at_stop']:,.2f} "
                f"({sizing.details['risk_pct']*100:.2f}% of equity, capped by {sizing.details['capped_by']})."
            )
        else:
            st.error(sizing.reason)
            qty = 0.0
    else:
        equity = account.get_equity({result.symbol: entry_price})
        max_notional = equity * rm.config.max_position_pct
        qty = max_notional / entry_price if entry_price > 0 else 0.0
        st.caption(f"Fixed notional size: {qty:.6f} units (${max_notional:,.2f}).")

    qty = st.number_input("Quantity (editable)", min_value=0.0, value=float(qty), format="%.6f")

    if st.button("Open paper position", type="primary"):
        check = account.validate_order(result.symbol, side, qty, entry_price)
        if not check:
            st.error(f"Order blocked: {check.reason}")
        else:
            account.open_position(
                symbol=result.symbol,
                market=result.market,
                side=side,
                quantity=qty,
                price=entry_price,
                strategy="manual",
                reason="Manual paper order",
                stop_loss=stop_price,
                take_profit=tp_price,
                timeframe=result.timeframe,
            )
            persist()
            st.success(f"Opened {side} {qty:.6f} {result.symbol} at ~{entry_price:,.4f}")
            st.rerun()

    st.divider()
    st.subheader("Open positions")
    open_positions = account.get_open_positions()
    if not open_positions:
        st.info("No open positions.")
    else:
        prices = {result.symbol: price}
        for p in open_positions:
            mark = prices.get(p.symbol, p.entry_price)
            upnl = p.unrealized_pnl
            st.write(
                f"**{p.symbol} {p.side}** qty {p.quantity:.6f} @ {p.entry_price:,.4f} "
                f"| mark {mark:,.4f} | uPnL ${upnl:,.2f} | stop {p.stop_loss} | target {p.take_profit}"
            )
            b = st.columns([1, 3])
            if b[0].button("Close", key=f"close_{p.id}"):
                pnl = account.close_position(p.id, mark, reason="manual close")
                persist()
                st.success(f"Closed for ${pnl:,.2f}")
                st.rerun()

    st.divider()
    st.subheader("Optional automatic paper trading")
    st.warning(
        "When enabled, the bot opens a paper trade whenever a BUY/SELL signal "
        "appears on the last closed candle. This is simulated automation only."
    )
    auto = st.toggle("Enable automatic paper trading", value=st.session_state.auto_trade)
    st.session_state.auto_trade = auto
    if auto and df is not None:
        signal = st.session_state.signal_service.generate_signal(df)
        if signal.action in ("BUY", "SELL") and not account.has_open_position(result.symbol):
            side = "LONG" if signal.action == "BUY" else "SHORT"
            stop_price = entry_price * (1 - rm.config.stop_loss_pct) if side == "LONG" else entry_price * (1 + rm.config.stop_loss_pct)
            sizing = rm.size_position(account.get_equity({result.symbol: entry_price}), entry_price, stop_price)
            if sizing:
                try:
                    account.open_position(
                        symbol=result.symbol, market=result.market, side=side,
                        quantity=sizing.details["quantity"], price=entry_price,
                        strategy="EMA_RSI", reason=f"Auto: {signal.reason}",
                        stop_loss=stop_price,
                        take_profit=entry_price * (1 + rm.config.take_profit_pct) if side == "LONG" else entry_price * (1 - rm.config.take_profit_pct),
                        timeframe=result.timeframe,
                    )
                    persist()
                    st.success(f"Auto-opened {side} on {result.symbol}.")
                    st.rerun()
                except ValueError as exc:
                    st.info(f"Auto-trade skipped: {exc}")
        else:
            st.info("No actionable signal on the last closed candle.")


def page_risk(sb, result):
    st.header("Risk Management")
    account = st.session_state.account
    rm = account.risk_manager
    cfg = rm.config

    st.caption("Risk controls persist across restarts and cannot be bypassed by refreshing.")
    col = st.columns(2)
    with col[0]:
        st.subheader("Configuration")
        max_pos = st.slider("Max position notional (% of equity)", 1, 100, int(cfg.max_position_pct * 100))
        max_risk = st.slider("Max risk per trade (% of equity)", 1, 20, int(cfg.max_risk_per_trade * 100))
        daily = st.slider("Daily loss limit (% of day-start equity)", 1, 50, int(cfg.daily_loss_limit * 100))
        max_open = st.number_input("Max open positions", 1, 20, cfg.max_open_positions)
        max_exposure = st.slider("Max total exposure (% of equity)", 1, 100, int(cfg.max_total_exposure_pct * 100))
        max_losses = st.number_input("Max consecutive losses", 1, 50, cfg.max_consecutive_losses)
        if st.button("Apply risk settings"):
            try:
                rm.config = RiskConfig(
                    max_position_pct=max_pos / 100,
                    max_risk_per_trade=max_risk / 100,
                    daily_loss_limit=daily / 100,
                    stop_loss_pct=cfg.stop_loss_pct,
                    take_profit_pct=cfg.take_profit_pct,
                    risk_reward=cfg.risk_reward,
                    max_open_positions=int(max_open),
                    max_total_exposure_pct=max_exposure / 100,
                    max_consecutive_losses=int(max_losses),
                    cooldown_candles=cfg.cooldown_candles,
                    emergency_pause=cfg.emergency_pause,
                ).validate()
                persist()
                st.success("Risk settings updated.")
            except ValueError as exc:
                st.error(f"Invalid settings: {exc}")
    with col[1]:
        st.subheader("Status")
        equity = account.get_equity({sb["symbol"]: result.last_price} if result.last_price else {})
        st.metric("Emergency pause", "ON" if rm.emergency_pause else "OFF")
        st.metric("Consecutive losses", rm.consecutive_losses)
        st.metric("Daily loss", f"${rm.daily_loss(equity):,.2f} ({rm.daily_loss_pct(equity)*100:.2f}%)")
        st.metric("Remaining allowance", f"${rm.remaining_daily_allowance(equity):,.2f}")
        st.write("A stop-loss reduces but does not eliminate risk. Gaps and slippage can cause larger losses than planned.")
        if st.button("Reset risk lockouts (audited)"):
            rm.reset_lockouts("user_reset")
            persist()
            st.success("Lockouts reset and recorded in the audit log.")
        if st.checkbox("Activate emergency pause"):
            rm.trigger_emergency_pause("user_activated")
            persist()
            st.rerun()


def page_strategy_lab(sb, result):
    st.header("Strategy Lab & Backtesting")
    st.warning("Backtesting results do NOT establish future profitability.")
    if not result.ok:
        st.warning(f"No data: {result.error}")
        return
    df = result.df

    c = st.columns(3)
    ema_fast = c[0].number_input("EMA fast", 2, 100, 9, key="lab_fast")
    ema_slow = c[1].number_input("EMA slow", 3, 200, 21, key="lab_slow")
    rsi_period = c[2].number_input("RSI period", 2, 50, 14, key="lab_rsi")
    c2 = st.columns(4)
    rsi_low = c2[0].number_input("RSI low", 0, 100, 30, key="lab_rlow")
    rsi_high = c2[1].number_input("RSI high", 0, 100, 70, key="lab_rhigh")
    use_trend = c2[2].checkbox("EMA50 trend filter", value=False, key="lab_trend")
    allow_short = c2[3].checkbox("Allow short trades", value=True, key="lab_short")
    c3 = st.columns(3)
    balance = c3[0].number_input("Starting balance", 1000.0, 1_000_000.0, float(settings.START_BALANCE), step=1000.0)
    stop_pct = c3[1].number_input("Stop loss %", 0.1, 50.0, 2.0, step=0.1)
    tp_pct = c3[2].number_input("Take profit %", 0.1, 100.0, 4.0, step=0.1)

    if st.button("Run backtest", type="primary"):
        strategy = get_strategy(
            "EMA_RSI",
            ema_fast=int(ema_fast), ema_slow=int(ema_slow), rsi_period=int(rsi_period),
            rsi_oversold=float(rsi_low), rsi_overbought=float(rsi_high),
            use_trend_filter=bool(use_trend),
        )
        risk_cfg = RiskConfig(
            stop_loss_pct=stop_pct / 100,
            take_profit_pct=tp_pct / 100,
            max_risk_per_trade=0.01,
            max_position_pct=0.05,
        ).validate()
        engine = BacktestEngine(initial_balance=balance, risk_config=risk_cfg)
        res = engine.run(df, strategy, market=sb["market"], symbol=sb["symbol"], timeframe=sb["timeframe"], allow_short=allow_short)
        if not res["ok"]:
            st.error(res["error"])
            return
        m = res["metrics"]
        st.subheader("Performance metrics")
        mcols = st.columns(4)
        mcols[0].metric("Net profit", f"${m['net_profit']:,.2f}")
        mcols[1].metric("Total return", f"{m['total_return_pct']:.2f}%")
        mcols[2].metric("Trades", m["total_trades"])
        mcols[3].metric("Win rate", f"{m['win_rate']:.1f}%")
        mcols2 = st.columns(4)
        mcols2[0].metric("Profit factor", f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "inf")
        mcols2[1].metric("Max drawdown", f"{m['max_drawdown_pct']:.2f}%")
        mcols2[2].metric("Avg win", f"${m['average_win']:,.2f}")
        mcols2[3].metric("Avg loss", f"${m['average_loss']:,.2f}")

        st.plotly_chart(equity_curve_figure(res["equity_curve"]), use_container_width=True)

        st.subheader("Trade-by-trade history")
        if res["trades"]:
            trade_df = pd.DataFrame(res["trades"])
            cols = [c for c in ["symbol", "side", "entry_time", "entry_price", "exit_time", "exit_price", "realized_pnl", "exit_reason", "fees"] if c in trade_df.columns]
            st.dataframe(trade_df[cols], use_container_width=True)
        else:
            st.info("No trades were generated by this configuration.")
        st.caption(
            "Execution rule: a signal at candle close is entered at the NEXT candle's open. "
            "If a candle touches both the stop and the target, the stop is assumed hit first (conservative)."
        )
        st.session_state["last_backtest"] = res


def page_journal(sb):
    st.header("Trade Journal")
    db = st.session_state.db
    rows = db.get_trades()
    if not rows:
        st.info("No trades recorded yet. Open a paper trade to populate the journal.")
        return
    df = pd.DataFrame(rows)
    st.caption(f"{len(df)} trades stored in the local SQLite database.")

    c = st.columns(4)
    symbol_filter = c[0].selectbox("Symbol", ["All"] + sorted(df["symbol"].dropna().unique().tolist()))
    side_filter = c[1].selectbox("Side", ["All"] + sorted(df["side"].dropna().unique().tolist()))
    status_filter = c[2].selectbox("Status", ["All"] + sorted(df["status"].dropna().unique().tolist()))
    strategy_filter = c[3].selectbox("Strategy", ["All"] + sorted(df["strategy"].dropna().unique().tolist()))

    view = df.copy()
    if symbol_filter != "All":
        view = view[view["symbol"] == symbol_filter]
    if side_filter != "All":
        view = view[view["side"] == side_filter]
    if status_filter != "All":
        view = view[view["status"] == status_filter]
    if strategy_filter != "All":
        view = view[view["strategy"] == strategy_filter]

    st.dataframe(view, use_container_width=True)
    csv = view.to_csv(index=False).encode("utf-8")
    st.download_button("Export filtered trades as CSV", csv, "trades.csv", "text/csv")


def page_learning(sb, result, service):
    st.header("Technical Analysis Learning Center")
    st.write(
        "Plain-language explanations for beginners. Nothing here predicts prices "
        "with certainty."
    )

    with st.expander("Candlestick anatomy"):
        st.write(
            "A candle shows the open, high, low, and close over a chosen period. "
            "The body spans open to close; the wicks show the extremes. Green "
            "(bullish) means close above open; red (bearish) means close below."
        )
    with st.expander("Support and resistance"):
        st.write(
            "Support is a price area where buyers have previously stepped in; "
            "resistance is where sellers have. They are zones, not exact lines, "
            "and they break."
        )
    with st.expander("EMA crossovers"):
        st.write(
            "An exponential moving average weights recent prices more. When a "
            "fast EMA crosses above a slow EMA it can indicate upward momentum; "
            "the reverse suggests downward momentum. Crossovers lag price."
        )
    with st.expander("RSI (Relative Strength Index)"):
        st.write(
            "RSI oscillates 0-100 and measures recent momentum. Values above 70 "
            "are often called 'overbought' and below 30 'oversold', but strong "
            "trends can stay extended for a long time."
        )
    with st.expander("MACD"):
        st.write(
            "MACD compares two EMAs. The MACD line crossing above its signal "
            "line suggests improving momentum; crossing below suggests weakening."
        )
    with st.expander("Stop-loss and take-profit"):
        st.write(
            "A stop-loss is a price at which you exit to limit a loss. A "
            "take-profit locks in a gain. A stop is not a guarantee: gaps and "
            "slippage can fill you at a worse price."
        )
    with st.expander("Risk-to-reward and position sizing"):
        st.write(
            "Risk-to-reward compares potential loss to potential gain. Position "
            "sizing sets quantity so the loss at your stop equals a small, fixed "
            "percentage of your account (for example 1%). Notional value and "
            "risk at the stop are different things."
        )
    with st.expander("Spread and slippage"):
        st.write(
            "The spread is the gap between buy and sell prices; slippage is the "
            "difference between expected and actual fill. Both are simulated in "
            "this app and reduce results."
        )

    st.divider()
    st.subheader("Patterns detected in the current data")
    if result.ok:
        events = st.session_state.signal_service.patterns(result.df, tail=10)
        if not events:
            st.info("No patterns detected in the current data.")
        for event in reversed(events):
            st.write(f"**{event['pattern']}** at {utc_str(event['timestamp'])} - {event['why']}")
    else:
        st.info("Load data to detect patterns.")


def page_settings(sb, result, service):
    st.header("Settings & Diagnostics")
    db = st.session_state.db
    c = st.columns(2)
    with c[0]:
        st.subheader("Data provider status")
        st.write(f"Selected market: {sb['market']} / {sb['symbol']} ({sb['timeframe']})")
        st.write(f"Last retrieval source: {result.source if result else 'N/A'}")
        st.write(f"Last candle (UTC): {utc_str(result.last_time) if result and result.ok else 'N/A'}")
        if result and result.error:
            st.error(f"Last error: {result.error}")
        st.write("Crypto provider: CCXT/Binance public endpoint (no keys).")
        st.write("Forex provider: yfinance (educational, may be delayed).")
        st.write("Offline fallback: clearly-labelled synthetic data.")
    with c[1]:
        st.subheader("Application")
        st.write(f"Version: {settings.APP_VERSION}")
        st.write(f"Database: {settings.DB_PATH}")
        st.write(f"Log file: {settings.LOG_PATH}")
        st.write("Paper mode only - real orders are impossible by design.")
        st.subheader("Backup")
        if st.button("Backup database now"):
            path = f"data/backup_{utcnow().strftime('%Y%m%d_%H%M%S')}.db"
            try:
                db.backup_to(path)
                st.success(f"Backed up to {path}")
            except Exception as exc:
                st.error(f"Backup failed: {exc}")

    st.divider()
    st.subheader("Danger zone")
    st.warning("Resetting the account deletes all simulated trades and resets the balance.")
    if st.button("Reset paper account"):
        if st.session_state.confirm_reset:
            st.session_state.repo.reset(st.session_state.account, "user_reset")
            st.session_state.confirm_reset = False
            st.success("Paper account reset.")
            st.rerun()
        else:
            st.session_state.confirm_reset = True
            st.error("Click 'Reset paper account' again to confirm.")

    st.divider()
    st.subheader("Event log (audit trail)")
    events = db.get_events(limit=25)
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True)
    else:
        st.caption("No events recorded yet.")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    init_state()
    service = st.session_state.market_service
    sb = sidebar(service)

    st.title(settings.APP_NAME)
    st.caption(
        "Educational paper-trading simulator for crypto and forex. "
        "NO real orders. NO API keys required."
    )

    result = get_data(sb["market"], sb["symbol"], sb["timeframe"], sb["limit"], sb["force_synthetic"])

    signal = None
    if result.ok and len(result.df) >= 55:
        signal = st.session_state.signal_service.generate_signal(result.df)

    page = sb["page"]
    if page == "Overview":
        page_overview(sb, result, signal)
    elif page == "Market Explorer":
        page_market_explorer(sb, service)
    elif page == "Chart":
        page_chart(sb, result)
    elif page == "Signal Center":
        page_signal_center(sb, result)
    elif page == "Paper Trading":
        page_paper_trading(sb, result)
    elif page == "Risk Management":
        page_risk(sb, result)
    elif page == "Strategy Lab":
        page_strategy_lab(sb, result)
    elif page == "Trade Journal":
        page_journal(sb)
    elif page == "Learning Center":
        page_learning(sb, result, service)
    elif page == "Settings & Diagnostics":
        page_settings(sb, result, service)

    st.sidebar.divider()
    st.sidebar.caption("Educational use only. Not financial advice.")


if __name__ == "__main__":
    main()