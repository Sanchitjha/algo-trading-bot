import logging
import MetaTrader5 as mt5
from config.settings import (
    MAX_DAILY_LOSS_PCT,
    MAX_OPEN_POSITIONS,
    MAX_RISK_PER_TRADE,
)


def calculate_lot_size(
    account_balance: float,
    risk_pct: float,
    symbol: str,
    sl_price: float,
    action: str,
) -> float:
    """
    Calculate position size so that a stop-loss hit = risk_pct% of balance.

    Formula:
        Risk Amount  = balance * (risk_pct / 100)
        Pip Value    = contract_size * tick_value / tick_size
        SL in pips   = abs(entry - sl_price) / point
        Lot Size     = Risk Amount / (SL in pips * pip_value_per_lot)
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        raise ValueError(f"Symbol {symbol} not found in MT5")

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise ValueError(f"Cannot get tick data for {symbol}")

    entry = tick.ask if action == 'buy' else tick.bid

    sl_pips = abs(entry - sl_price) / info.point
    if sl_pips == 0:
        raise ValueError("Stop loss distance is zero — cannot calculate lot size")

    risk_amount   = account_balance * (risk_pct / 100)
    pip_value     = info.trade_contract_size * info.trade_tick_value / info.trade_tick_size
    pip_value_lot = pip_value / 10  # Per standard lot

    raw_lot = risk_amount / (sl_pips * pip_value_lot)

    # Clamp to broker's allowed range and round to step
    lot_step = info.volume_step
    lot_min  = info.volume_min
    lot_max  = info.volume_max

    lot = round(raw_lot / lot_step) * lot_step
    lot = max(lot_min, min(lot_max, lot))

    logging.info(
        f"Lot calc: balance={account_balance}, risk={risk_pct}%, "
        f"SL_pips={sl_pips:.1f}, raw={raw_lot:.4f}, final={lot:.2f}"
    )
    return round(lot, 2)


def check_risk_limits(
    account_balance: float,
    daily_pnl: float,
    open_positions: int,
    risk_pct: float,
) -> tuple[bool, str]:
    """
    Pre-trade risk gate.
    Returns (allowed, reason).
    """
    daily_loss_pct = abs(daily_pnl / account_balance * 100) if account_balance > 0 else 0

    if daily_loss_pct >= MAX_DAILY_LOSS_PCT:
        return False, f"Daily loss limit reached ({daily_loss_pct:.1f}% >= {MAX_DAILY_LOSS_PCT}%) — trading halted"

    if open_positions >= MAX_OPEN_POSITIONS:
        return False, f"Max {MAX_OPEN_POSITIONS} open positions reached (current: {open_positions})"

    if risk_pct > MAX_RISK_PER_TRADE:
        return False, f"Risk {risk_pct}% exceeds max {MAX_RISK_PER_TRADE}% per trade"

    return True, "OK"


def calculate_daily_pnl() -> float:
    """Calculate today's realized + unrealized P&L from MT5."""
    from datetime import datetime, timedelta

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Closed trades today
    deals = mt5.history_deals_get(today_start, datetime.now())
    closed_pnl = sum(d.profit for d in deals) if deals else 0.0

    # Open position unrealized P&L
    positions = mt5.positions_get()
    open_pnl = sum(p.profit for p in positions) if positions else 0.0

    return closed_pnl + open_pnl
