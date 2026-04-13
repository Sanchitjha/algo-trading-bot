"""
Algo Trading Bot — Main Flask Server (Full Integration)
========================================================
Receives TradingView webhook alerts (JSON or PineConnector format),
validates signals, applies session/news/correlation filters, calculates
position sizing, places orders via MT5, manages trailing stops,
and sends Telegram notifications.

Endpoints:
    POST /webhook         — Main signal receiver
    POST /pineconnector   — PineConnector text alert receiver
    POST /emergency/close — Close all positions immediately
    POST /emergency/halt  — Halt all trading
    POST /emergency/resume— Resume trading
    GET  /health          — Health check
    GET  /positions       — Open positions
    GET  /account         — Account info
    GET  /status          — Full system status
"""

from flask import Flask, request, jsonify
import logging
import hashlib
import hmac
import MetaTrader5 as mt5

from config.settings import WEBHOOK_SECRET, PORT, LOG_LEVEL, BOT_VERSION
from bot.broker import BrokerClient
from bot.risk import calculate_lot_size, check_risk_limits, calculate_daily_pnl
from bot.signals import validate_signal, parse_signal
from bot.pineconnector import parse_pineconnector_alert
from bot.session_filter import can_trade_now
from bot.correlation_guard import check_correlation_limit
from bot.trailing_stop import TrailingStopManager
from bot.emergency import close_all_positions, cancel_all_pending_orders, trading_halt
from bot.telegram import (
    send_telegram,
    format_trade_message,
    send_startup_message,
    send_error_alert,
)

# ─── APP SETUP ───────────────────────────────────────────────
app = Flask(__name__)

logging.basicConfig(
    filename='logs/trades.log',
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
)
# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

broker = BrokerClient()
trailing_manager = TrailingStopManager(check_interval=30)


# ─── SECURITY ────────────────────────────────────────────────
def verify_signature(payload: bytes, secret: str) -> bool:
    """Verify webhook authenticity via HMAC-SHA256 signature."""
    if not secret:
        return True
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    received = request.headers.get('X-Signature', '')
    return hmac.compare_digest(expected, received)


# ─── CORE TRADE EXECUTION ───────────────────────────────────
def execute_trade(signal: dict) -> tuple[dict, int]:
    """
    Core trade execution logic shared by webhook and pineconnector endpoints.
    Returns (response_dict, http_status).
    """
    action = signal['action']
    symbol = signal['symbol']

    # ── Handle close commands ──
    if action in ('closelong', 'closeshort', 'close_all'):
        results = broker.close_all_by_symbol(symbol)
        msg = f"Closed {len(results)} position(s) for {symbol}"
        send_telegram(msg)
        logging.info(msg)
        return {'status': 'closed', 'count': len(results)}, 200

    # ── Check trading halt ──
    halt_ok, halt_reason = trading_halt.check()
    if not halt_ok:
        logging.warning(f"Trading halted: {halt_reason}")
        return {'status': 'halted', 'reason': halt_reason}, 200

    # ── Session filter ──
    session_ok, session_reason = can_trade_now()
    if not session_ok:
        logging.info(f"Session filter blocked: {session_reason}")
        return {'status': 'blocked', 'reason': session_reason}, 200

    # ── Correlation guard ──
    corr_ok, corr_reason = check_correlation_limit(symbol, action)
    if not corr_ok:
        logging.warning(f"Correlation blocked: {corr_reason}")
        send_telegram(f"Trade blocked (correlation): {corr_reason}")
        return {'status': 'blocked', 'reason': corr_reason}, 200

    # ── Pre-trade risk check ──
    account_info   = broker.get_account_info()
    daily_pnl      = calculate_daily_pnl()
    open_positions = len(broker.get_open_positions())

    allowed, reason = check_risk_limits(
        account_balance=account_info['balance'],
        daily_pnl=daily_pnl,
        open_positions=open_positions,
        risk_pct=signal['risk_pct'],
    )

    if not allowed:
        logging.warning(f"Risk limit blocked trade: {reason}")
        send_telegram(f"Trade blocked: {reason}")
        return {'status': 'blocked', 'reason': reason}, 200

    # ── Calculate lot size ──
    sl_price = signal['sl']
    tp_price = signal['tp']

    if sl_price is None:
        logging.error("No stop loss provided — cannot calculate lot size")
        return {'error': 'Stop loss is required'}, 400

    lot_size = calculate_lot_size(
        account_balance=account_info['balance'],
        risk_pct=signal['risk_pct'],
        symbol=symbol,
        sl_price=sl_price,
        action=action,
    )

    # ── Place the order ──
    result = broker.place_order(
        action=action,
        symbol=symbol,
        lot=lot_size,
        sl=sl_price,
        tp=tp_price,
        comment=signal.get('comment', 'Algo Bot'),
    )

    if result['success']:
        msg = format_trade_message(
            action=action,
            symbol=symbol,
            lot=lot_size,
            price=result['price'],
            sl=sl_price,
            tp=tp_price,
            ticket=result['ticket'],
        )
        send_telegram(msg)
        logging.info(f"Order placed: {action.upper()} {symbol} {lot_size} lots | ticket={result['ticket']}")
        return {
            'status': 'executed',
            'ticket': result['ticket'],
            'price':  result['price'],
            'lot':    lot_size,
        }, 200
    else:
        error_msg = f"Order FAILED {action.upper()} {symbol}: {result['error']}"
        send_error_alert(error_msg)
        logging.error(error_msg)
        return {'status': 'failed', 'error': result['error']}, 500


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint — receives TradingView JSON alerts."""
    raw = request.get_data()

    if not verify_signature(raw, WEBHOOK_SECRET):
        logging.warning("Unauthorized webhook attempt blocked")
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    logging.info(f"Signal received: {data}")

    is_valid, error = validate_signal(data)
    if not is_valid:
        logging.error(f"Invalid signal: {error}")
        return jsonify({'error': error}), 400

    signal = parse_signal(data)
    response, status = execute_trade(signal)
    return jsonify(response), status


@app.route('/pineconnector', methods=['POST'])
def pineconnector():
    """PineConnector text alert endpoint (Route A format)."""
    raw = request.get_data()

    if not verify_signature(raw, WEBHOOK_SECRET):
        return jsonify({'error': 'Unauthorized'}), 401

    raw_text = raw.decode('utf-8').strip()
    logging.info(f"PineConnector alert: {raw_text}")

    signal = parse_pineconnector_alert(raw_text)
    if signal is None:
        return jsonify({'error': 'Invalid PineConnector format'}), 400

    # ── Convert sl_pips / tp_pips → absolute price ──────────────
    # PineConnector alerts may send pips instead of absolute prices.
    # We resolve the current price from MT5 and compute absolute SL/TP.
    if signal.get('sl') is None and signal.get('sl_pips') is not None:
        symbol = signal['symbol']
        action = signal['action']
        if action in ('buy', 'sell'):
            tick     = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if tick and sym_info:
                entry     = tick.ask if action == 'buy' else tick.bid
                pip_size  = sym_info.point * 10   # 1 pip = 10 points for most pairs
                sl_pips   = signal.pop('sl_pips', 0)
                tp_pips   = signal.pop('tp_pips', 0)
                if action == 'buy':
                    signal['sl'] = round(entry - sl_pips * pip_size, 5)
                    signal['tp'] = round(entry + tp_pips * pip_size, 5)
                else:
                    signal['sl'] = round(entry + sl_pips * pip_size, 5)
                    signal['tp'] = round(entry - tp_pips * pip_size, 5)
                logging.info(
                    f"PineConnector pips resolved: entry={entry}, "
                    f"SL={signal['sl']}, TP={signal['tp']}"
                )
            else:
                return jsonify({'error': f'Cannot get tick data for {symbol}'}), 500

    response, status = execute_trade(signal)
    return jsonify(response), status


# ─── EMERGENCY ENDPOINTS ────────────────────────────────────

@app.route('/emergency/close', methods=['POST'])
def emergency_close():
    """Close ALL open positions immediately."""
    logging.warning("EMERGENCY CLOSE triggered via API")
    result = close_all_positions()
    cancel_all_pending_orders()
    return jsonify(result), 200


@app.route('/emergency/halt', methods=['POST'])
def halt():
    """Halt all new trading (existing positions stay open)."""
    reason = request.json.get('reason', 'Manual halt via API') if request.is_json else 'Manual halt'
    trading_halt.halt(reason)
    return jsonify({'status': 'halted', 'reason': reason}), 200


@app.route('/emergency/resume', methods=['POST'])
def resume():
    """Resume trading after a halt."""
    trading_halt.resume()
    return jsonify({'status': 'resumed'}), 200


# ─── INFO ENDPOINTS ─────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for cloud monitoring."""
    mt5_status = broker.is_connected()
    positions  = broker.get_open_positions()
    return jsonify({
        'status':         'running',
        'version':        BOT_VERSION,
        'mt5_connected':  mt5_status,
        'open_positions': len(positions),
        'trading_halted': trading_halt.is_halted,
    })


@app.route('/positions', methods=['GET'])
def positions():
    """Return all open positions."""
    return jsonify({'positions': broker.get_open_positions()})


@app.route('/account', methods=['GET'])
def account():
    """Return account info."""
    return jsonify(broker.get_account_info())


@app.route('/status', methods=['GET'])
def status():
    """Full system status — account, positions, risk, session, halt state."""
    account_info = broker.get_account_info()
    open_pos     = broker.get_open_positions()
    daily_pnl    = calculate_daily_pnl()
    session_ok, session_reason = can_trade_now()
    halt_ok, halt_reason = trading_halt.check()

    return jsonify({
        'version':          BOT_VERSION,
        'mt5_connected':    broker.is_connected(),
        'account':          account_info,
        'open_positions':   len(open_pos),
        'positions':        open_pos,
        'daily_pnl':        round(daily_pnl, 2),
        'session_active':   session_ok,
        'session_info':     session_reason,
        'trading_allowed':  halt_ok,
        'halt_reason':      halt_reason,
        'trailing_stop':    trailing_manager.running,
    })


# ─── STARTUP ─────────────────────────────────────────────────
if __name__ == '__main__':
    send_startup_message()
    trailing_manager.start()
    app.run(host='0.0.0.0', port=PORT)
