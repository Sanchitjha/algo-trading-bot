import MetaTrader5 as mt5
import logging
import time
from config.settings import MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER


class BrokerClient:
    """MetaTrader 5 broker connection and order management."""

    def __init__(self):
        self.account  = MT5_ACCOUNT
        self.password = MT5_PASSWORD
        self.server   = MT5_SERVER
        self._connect()

    def _connect(self):
        """Initialize MT5 connection with retry logic."""
        for attempt in range(3):
            if not mt5.initialize():
                logging.warning(f"MT5 init failed (attempt {attempt + 1}/3)")
                time.sleep(5)
                continue
            if mt5.login(self.account, self.password, self.server):
                logging.info(f"Connected to MT5: {self.server} | Account: {self.account}")
                return
            logging.error(f"MT5 login failed: {mt5.last_error()}")
        raise ConnectionError("Could not connect to MT5 after 3 attempts")

    def is_connected(self) -> bool:
        return mt5.terminal_info() is not None

    def get_account_info(self) -> dict:
        info = mt5.account_info()
        if info is None:
            self._connect()
            info = mt5.account_info()
        return {
            'balance':  info.balance,
            'equity':   info.equity,
            'margin':   info.margin,
            'profit':   info.profit,
            'currency': info.currency,
        }

    def place_order(self, action: str, symbol: str, lot: float,
                    sl: float, tp: float, comment: str = "") -> dict:
        """Place market order with SL/TP. Returns result dict."""
        if not self.is_connected():
            self._connect()

        # Ensure symbol is available in Market Watch
        if not mt5.symbol_select(symbol, True):
            return {'success': False, 'error': f"Symbol {symbol} not available"}

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {'success': False, 'error': f"Cannot get price for {symbol}"}

        order_type = mt5.ORDER_TYPE_BUY if action == 'buy' else mt5.ORDER_TYPE_SELL
        price      = tick.ask if action == 'buy' else tick.bid
        deviation  = 20  # Max slippage in points

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       float(lot),
            "type":         order_type,
            "price":        price,
            "sl":           float(sl) if sl else 0.0,
            "tp":           float(tp) if tp else 0.0,
            "deviation":    deviation,
            "magic":        20240101,
            "comment":      comment,
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        logging.info(f"Sending order: {action.upper()} {symbol} {lot} lots @ {price}")
        result = mt5.order_send(request)

        if result is None:
            return {'success': False, 'error': f"order_send returned None: {mt5.last_error()}"}

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"Order executed: ticket={result.order}, price={result.price}")
            return {
                'success': True,
                'ticket':  result.order,
                'price':   result.price,
                'volume':  result.volume,
            }

        # Handle requote — retry once with updated price
        if result.retcode == mt5.TRADE_RETCODE_REQUOTE:
            logging.warning("Requote received, retrying with new price...")
            tick = mt5.symbol_info_tick(symbol)
            request['price'] = tick.ask if action == 'buy' else tick.bid
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                return {
                    'success': True,
                    'ticket':  result.order,
                    'price':   result.price,
                    'volume':  result.volume,
                }

        return {
            'success': False,
            'error':   f"Code {result.retcode}: {result.comment}",
            'retcode': result.retcode,
        }

    def close_position(self, ticket: int) -> dict:
        """Close an open position by ticket number."""
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return {'success': False, 'error': 'Position not found'}

        pos        = position[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        tick       = mt5.symbol_info_tick(pos.symbol)
        price      = tick.bid if pos.type == 0 else tick.ask

        request = {
            "action":    mt5.TRADE_ACTION_DEAL,
            "symbol":    pos.symbol,
            "volume":    pos.volume,
            "type":      close_type,
            "position":  ticket,
            "price":     price,
            "deviation": 20,
            "magic":     pos.magic,
            "comment":   "Bot close",
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"Position {ticket} closed at {result.price}")
            return {'success': True, 'ticket': ticket, 'price': result.price}
        return {
            'success': False,
            'error': f"Close failed: {result.retcode if result else 'None'}"
        }

    def close_all_by_symbol(self, symbol: str) -> list[dict]:
        """Close all open positions for a given symbol."""
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return []
        return [self.close_position(p.ticket) for p in positions]

    def get_open_positions(self) -> list[dict]:
        """Return all open positions as list of dicts."""
        positions = mt5.positions_get()
        if not positions:
            return []
        return [{
            'ticket': p.ticket,
            'symbol': p.symbol,
            'type':   'buy' if p.type == 0 else 'sell',
            'volume': p.volume,
            'profit': p.profit,
            'price':  p.price_open,
            'sl':     p.sl,
            'tp':     p.tp,
            'magic':  p.magic,
        } for p in positions]
