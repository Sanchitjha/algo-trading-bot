"""
Phase 4 — Trailing Stop Manager
=================================
Monitors open positions and adjusts stop loss to lock in profits.

Rules (from documentation):
  - Move SL to breakeven when trade is +1R in profit
  - Optional: trail SL behind price at ATR distance
"""

import logging
import time
import threading

import MetaTrader5 as mt5

from config.strategy_rules import EXIT_RULES


class TrailingStopManager:
    """Background thread that monitors and adjusts stop losses."""

    def __init__(self, check_interval: int = 30):
        """
        Args:
            check_interval: Seconds between each position check
        """
        self.check_interval = check_interval
        self.running = False
        self._thread = None

    def start(self):
        """Start the trailing stop monitor in a background thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logging.info("Trailing stop manager started")

    def stop(self):
        """Stop the trailing stop monitor."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=10)
        logging.info("Trailing stop manager stopped")

    def _run_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._check_positions()
            except Exception as e:
                logging.error(f"Trailing stop error: {e}")
            time.sleep(self.check_interval)

    def _check_positions(self):
        """Check all open positions and adjust SL where needed."""
        positions = mt5.positions_get()
        if not positions:
            return

        for pos in positions:
            # Only manage positions opened by our bot (magic number check)
            if pos.magic != 20240101:
                continue

            self._manage_position(pos)

    def _manage_position(self, pos):
        """Apply trailing stop logic to a single position."""
        symbol = pos.symbol
        ticket = pos.ticket
        entry_price = pos.price_open
        current_sl  = pos.sl
        current_tp  = pos.tp

        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return

        current_price = tick.bid if pos.type == 0 else tick.ask  # bid for longs, ask for shorts
        is_long = pos.type == 0

        # Calculate R-multiple (how many R's in profit)
        if current_sl == 0:
            return  # No SL set, can't calculate R

        sl_distance = abs(entry_price - current_sl)
        if sl_distance == 0:
            return

        if is_long:
            profit_distance = current_price - entry_price
        else:
            profit_distance = entry_price - current_price

        r_multiple = profit_distance / sl_distance

        # ── Rule 1: Move to breakeven at trigger R ──
        trigger_r = EXIT_RULES.get('trailing_trigger', 1.0)

        if r_multiple >= trigger_r and EXIT_RULES.get('trailing_stop', True):
            # Calculate new SL (breakeven + small buffer)
            info = mt5.symbol_info(symbol)
            buffer = info.point * 5 if info else 0  # 5 points above breakeven

            if is_long:
                new_sl = entry_price + buffer
                if new_sl > current_sl:
                    self._modify_sl(ticket, symbol, new_sl, current_tp)
            else:
                new_sl = entry_price - buffer
                if new_sl < current_sl or current_sl == 0:
                    self._modify_sl(ticket, symbol, new_sl, current_tp)

        # ── Rule 2: Trail SL behind price (at +2R) ──
        if r_multiple >= 2.0:
            atr_trail = self._get_atr_trail(symbol)
            if atr_trail > 0:
                if is_long:
                    trail_sl = current_price - atr_trail
                    if trail_sl > current_sl:
                        self._modify_sl(ticket, symbol, trail_sl, current_tp)
                else:
                    trail_sl = current_price + atr_trail
                    if trail_sl < current_sl:
                        self._modify_sl(ticket, symbol, trail_sl, current_tp)

    def _modify_sl(self, ticket: int, symbol: str, new_sl: float, tp: float):
        """Send SL modification request to MT5."""
        request = {
            "action":    mt5.TRADE_ACTION_SLTP,
            "symbol":    symbol,
            "position":  ticket,
            "sl":        round(new_sl, 5),
            "tp":        round(tp, 5) if tp else 0.0,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"Trailing SL updated: ticket={ticket}, new_sl={new_sl:.5f}")
        else:
            code = result.retcode if result else 'None'
            logging.warning(f"Failed to update SL for ticket={ticket}: retcode={code}")

    def _get_atr_trail(self, symbol: str) -> float:
        """Get current ATR value for trailing distance."""
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 15)
        if rates is None or len(rates) < 14:
            return 0.0

        # Simple ATR calculation
        import numpy as np
        highs  = np.array([r['high'] for r in rates])
        lows   = np.array([r['low'] for r in rates])
        closes = np.array([r['close'] for r in rates])

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )

        atr = np.mean(tr[-14:])
        return atr * EXIT_RULES.get('sl_atr_multiplier', 1.5)
