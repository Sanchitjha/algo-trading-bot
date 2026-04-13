"""
Phase 4 — Emergency Controls
==============================
Close all positions, halt trading, and panic-button functionality.
"""

import logging

import MetaTrader5 as mt5

from bot.telegram import send_telegram


def close_all_positions() -> dict:
    """
    EMERGENCY: Close every open position immediately.
    Returns summary of what was closed.
    """
    positions = mt5.positions_get()
    if not positions:
        msg = "Emergency close: No open positions found"
        logging.info(msg)
        send_telegram(msg)
        return {'closed': 0, 'failed': 0, 'details': []}

    closed = 0
    failed = 0
    details = []

    for pos in positions:
        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            failed += 1
            details.append({'ticket': pos.ticket, 'status': 'FAILED', 'reason': 'No tick data'})
            continue

        price = tick.bid if pos.type == 0 else tick.ask

        request = {
            "action":    mt5.TRADE_ACTION_DEAL,
            "symbol":    pos.symbol,
            "volume":    pos.volume,
            "type":      close_type,
            "position":  pos.ticket,
            "price":     price,
            "deviation": 50,  # Higher deviation for emergency
            "magic":     pos.magic,
            "comment":   "EMERGENCY CLOSE",
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
            details.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type':   'buy' if pos.type == 0 else 'sell',
                'volume': pos.volume,
                'profit': pos.profit,
                'status': 'CLOSED',
            })
            logging.info(f"Emergency closed: {pos.symbol} ticket={pos.ticket} P&L={pos.profit:.2f}")
        else:
            failed += 1
            details.append({
                'ticket': pos.ticket,
                'status': 'FAILED',
                'reason': f"retcode={result.retcode if result else 'None'}"
            })

    total_pnl = sum(d.get('profit', 0) for d in details if d['status'] == 'CLOSED')

    msg = (
        f"EMERGENCY CLOSE EXECUTED\n"
        f"Closed: {closed} | Failed: {failed}\n"
        f"Total P&L: {total_pnl:+.2f}"
    )
    logging.warning(msg)
    send_telegram(f"\U0001f6a8 {msg}")

    return {'closed': closed, 'failed': failed, 'total_pnl': total_pnl, 'details': details}


def cancel_all_pending_orders() -> dict:
    """Cancel all pending orders (limit/stop orders not yet filled)."""
    orders = mt5.orders_get()
    if not orders:
        return {'cancelled': 0}

    cancelled = 0
    for order in orders:
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order":  order.ticket,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            cancelled += 1
            logging.info(f"Cancelled pending order: ticket={order.ticket}")

    send_telegram(f"Cancelled {cancelled} pending orders")
    return {'cancelled': cancelled}


class TradingHalt:
    """
    Trading halt mechanism — prevents new trades while allowing
    existing positions to be managed.
    """

    def __init__(self):
        self._halted = False
        self._reason = ""

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def reason(self) -> str:
        return self._reason

    def halt(self, reason: str = "Manual halt"):
        """Halt all new trading."""
        self._halted = True
        self._reason = reason
        msg = f"TRADING HALTED: {reason}"
        logging.warning(msg)
        send_telegram(f"\U0001f6d1 {msg}")

    def resume(self):
        """Resume trading."""
        self._halted = False
        self._reason = ""
        msg = "Trading resumed"
        logging.info(msg)
        send_telegram(f"\u2705 {msg}")

    def check(self) -> tuple[bool, str]:
        """Check if trading is allowed. Returns (allowed, reason)."""
        if self._halted:
            return False, f"Trading halted: {self._reason}"
        return True, "OK"


# Global instance
trading_halt = TradingHalt()
