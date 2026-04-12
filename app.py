"""
Algo Trading Bot — Main Flask Server
=====================================
Receives TradingView webhook alerts, validates signals, calculates
position sizing, places orders via MT5, and sends Telegram notifications.
"""

from flask import Flask, request, jsonify
import logging
import hashlib
import hmac

from config.settings import WEBHOOK_SECRET, PORT, LOG_LEVEL, BOT_VERSION
from bot.broker import BrokerClient
from bot.risk import calculate_lot_size, check_risk_limits, calculate_daily_pnl
from bot.signals import validate_signal, parse_signal
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


# ─── SECURITY ────────────────────────────────────────────────
def verify_signature(payload: bytes, secret: str) -> bool:
    """Verify webhook authenticity via HMAC-SHA256 signature."""
    if not secret:
        return True  # Skip check if no secret configured
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    received = request.headers.get('X-Signature', '')
    return hmac.compare_digest(expected, received)


# ─── WEBHOOK ENDPOINT ────────────────────────────────────────
@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint — receives TradingView alerts."""
    raw = request.get_data()

    # Security check
    if not verify_signature(raw, WEBHOOK_SECRET):
        logging.warning("Unauthorized webhook attempt blocked")
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    logging.info(f"Signal received: {data}")

    # ── Validate signal ──
    is_valid, error = validate_signal(data)
    if not is_valid:
        logging.error(f"Invalid signal: {error}")
        return jsonify({'error': error}), 400

    signal = parse_signal(data)
    action = signal['action']
    symbol = signal['symbol']

    # ── Handle close commands ──
    if action in ('closelong', 'closeshort', 'close_all'):
        results = broker.close_all_by_symbol(symbol)
        msg = f"Closed {len(results)} position(s) for {symbol}"
        send_telegram(msg)
        logging.info(msg)
        return jsonify({'status': 'closed', 'count': len(results)}), 200

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
        return jsonify({'status': 'blocked', 'reason': reason}), 200

    # ── Calculate lot size ──
    sl_price = signal['sl']
    tp_price = signal['tp']

    if sl_price is None:
        logging.error("No stop loss provided — cannot calculate lot size")
        return jsonify({'error': 'Stop loss is required'}), 400

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
        comment=signal['comment'],
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
        return jsonify({
            'status': 'executed',
            'ticket': result['ticket'],
            'price':  result['price'],
            'lot':    lot_size,
        }), 200
    else:
        error_msg = f"Order FAILED {action.upper()} {symbol}: {result['error']}"
        send_error_alert(error_msg)
        logging.error(error_msg)
        return jsonify({'status': 'failed', 'error': result['error']}), 500


# ─── HEALTH CHECK ────────────────────────────────────────────
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
    })


# ─── POSITIONS ENDPOINT ─────────────────────────────────────
@app.route('/positions', methods=['GET'])
def positions():
    """Return all open positions."""
    return jsonify({'positions': broker.get_open_positions()})


# ─── ACCOUNT ENDPOINT ───────────────────────────────────────
@app.route('/account', methods=['GET'])
def account():
    """Return account info."""
    return jsonify(broker.get_account_info())


# ─── STARTUP ─────────────────────────────────────────────────
if __name__ == '__main__':
    send_startup_message()
    app.run(host='0.0.0.0', port=PORT)
